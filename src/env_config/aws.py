import configparser
from dataclasses import dataclass
import datetime as dt
import json
import logging
from os import environ
from pathlib import Path

import boto3
import serde
from serde.msgpack import from_msgpack, to_msgpack

from . import utils


log = logging.getLogger(__name__)

AWS_CONFIG_FPATH = Path('~/.aws/config').expanduser()


@dataclass
class ProfileConfig:
    profile: str
    op_ref_base: str
    mfa_serial: str


def profile_config(profile, *, config_fpath=None) -> ProfileConfig:
    """Parse AWS config file for given profile's information"""

    env_config_file = environ.get('AWS_CONFIG_FILE', config_fpath)
    aws_config_fpath = Path(env_config_file) if env_config_file else AWS_CONFIG_FPATH

    config = configparser.ConfigParser()
    config.read(aws_config_fpath)

    profile_conf = config[f'profile {profile}']
    op_prefix = profile_conf['envconfig_1pass']

    return ProfileConfig(profile, op_prefix, profile_conf['mfa_serial'])


@dataclass
class AWSAuth:
    """Permanent credentials needed to generate a temporary session"""

    access_key_id: str
    secret_key: str
    mfa_serial: str
    mfa_code: str | None


def op_auth(op_ref_base: str, mfa_serial: str = ''):
    op_ref_base = op_ref_base.rstrip('/')
    op_access_key = f'{op_ref_base}/access-key-id'
    op_secret_key = f'{op_ref_base}/secret-access-key'

    mfa_code = None
    if mfa_serial:
        op_mfa_ref = f'{op_ref_base}/Security/one-time password?attribute=otp'
        mfa_code = utils.op_read(op_mfa_ref)

    return AWSAuth(
        utils.op_read(op_access_key),
        utils.op_read(op_secret_key),
        mfa_serial,
        mfa_code,
    )


@serde.serde
class SessCreds:
    """Temporary session credentials"""

    access_key_id: str
    secret_key: str
    session_token: str
    expiration: dt.datetime

    def to_env_dict(self):
        return {
            'AWS_ACCESS_KEY_ID': self.access_key_id,
            'AWS_SECRET_ACCESS_KEY': self.secret_key,
            'AWS_SESSION_TOKEN': self.session_token,
            'AWS_SESSION_EXPIRATION': self.expiration.strftime('%Y-%m-%dT%H:%M:%SZ'),
        }

    def cli_json(self):
        return json.dumps(
            {
                'Version': 1,
                'AccessKeyId': self.access_key_id,
                'SecretAccessKey': self.secret_key,
                'SessionToken': self.session_token,
                'Expiration': self.expiration.isoformat(),
            },
        )


def sts_session(auth: AWSAuth) -> SessCreds:
    session = boto3.Session(
        aws_access_key_id=auth.access_key_id,
        aws_secret_access_key=auth.secret_key,
    )
    sts_client = session.client('sts')
    response = sts_client.get_session_token(
        # TODO: we should be able to change this but I'm not sure where that should live?  A custom
        # value in the AWS config profile?  env-config.yaml?
        DurationSeconds=3600,
        SerialNumber=auth.mfa_serial,
        TokenCode=auth.mfa_code,
    )
    creds = response['Credentials']
    return SessCreds(
        creds['AccessKeyId'],
        creds['SecretAccessKey'],
        creds['SessionToken'],
        creds['Expiration'],
    )


def op_sess_creds(op_ref_base: str, mfa_serial: str = '', _cache_dpath: Path | None = None):
    """
    Given a 1Pass item reference, return session credentials.  Cache session credentials
    in encrypted file to avoid the delay of 1Pass lookup + session gen.
    """
    enc_tmp = utils.EncryptedTempFile(op_ref_base + mfa_serial, dpath=_cache_dpath)
    if enc_tmp.exists():
        try:
            creds: SessCreds = from_msgpack(SessCreds, enc_tmp.read())

            # If the creds expire within the next five minutes, regenerate them
            if creds.expiration > utils.utc_now_in(minutes=5):
                log.info('Using cached credentials from %s', enc_tmp.fpath)
                return creds
            else:
                log.info('Cached credentials existed but have expired or will soon')
        except Exception:
            log.exception('Error getting encrypted cached credentials')
    else:
        log.info('No cached credentials existed.')

    perm_auth = op_auth(op_ref_base, mfa_serial)
    sess_auth = sts_session(perm_auth)

    log.info('Saving credential cache to %s', enc_tmp.fpath)
    enc_tmp.save(to_msgpack(sess_auth))

    return sess_auth
