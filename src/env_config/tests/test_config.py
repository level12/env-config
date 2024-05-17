from pathlib import Path
from unittest import mock

from env_config import config


configs = Path(__file__).parent / 'configs'


def load(fname):
    with configs.joinpath(fname).open() as fo:
        config.load(fo)


class TestConfig:
    @mock.patch.dict(config.environ, {'DB_PASS': '123'})
    def test_vars_and_env(self):
        conf = config.load(configs / 'vars-and-env.yaml')
        # As dict
        assert conf['profile']['bar']['BAZ1'] == 'b1'

        # Like LazyDict
        assert conf.profile.bar.BAZ1 == 'b1'
        assert conf.profile.bar.BAZ2 == 'b2'

        # Interpolation
        assert conf.profile.aws.key == 'private/key'
        assert conf.profile.aws.secret == 'private/secret'

        # From environment
        assert conf.profile.db.password == '123/456'

    @mock.patch.dict(config.environ, {'DB_PASS': '123'})
    def test_aws_profile(self):
        conf = config.load(configs / 'aws.yaml')

        assert dict(conf['profile']['aws.level12']) == {
            'AWS_ACCESS_KEY_ID': 'aws-vault://level12/AWS_ACCESS_KEY_ID',
            'AWS_SECRET_ACCESS_KEY': 'aws-vault://level12/AWS_SECRET_ACCESS_KEY',
            'AWS_SESSION_TOKEN': 'aws-vault://level12/AWS_SESSION_TOKEN',
            'AWS_SECURITY_TOKEN': 'aws-vault://level12/AWS_SECURITY_TOKEN',
            'AWS_VAULT': 'aws-vault://level12/AWS_VAULT',
            'AWS_SESSION_EXPIRATION': 'aws-vault://level12/AWS_SESSION_EXPIRATION',
        }
