from pathlib import Path
from unittest import mock

from env_config import aws, utils
from env_config.libs.testing import patch_obj


configs = Path(__file__).parent / 'configs'


class TestAWS:
    def test_profile_config(self):
        config = aws.profile_config(profile='starfleet', config_fpath=configs / 'aws-config')

        assert config.mfa_serial == 'arn:aws:iam::123456789:mfa/engineering'
        assert config.op_ref_base == 'op://Employee/starfleet-aws/'
        assert config.profile == 'starfleet'

    @patch_obj(aws.utils, 'op_read')
    def test_op_auth(self, m_op_read):
        m_op_read.side_effect = ('123456', 'key-id', 'secret')
        auth = aws.op_auth('op://Private/aws', 'arn...mfa/phaser')
        assert auth.access_key_id == 'key-id'
        assert auth.secret_key == 'secret'
        assert auth.mfa_serial == 'arn...mfa/phaser'
        assert auth.mfa_code == '123456'

        assert m_op_read.mock_calls == [
            mock.call('op://Private/aws/Security/one-time password?attribute=otp'),
            mock.call('op://Private/aws/access-key-id'),
            mock.call('op://Private/aws/secret-access-key'),
        ]

    @patch_obj(aws.utils, 'op_read')
    def test_op_auth_no_mfa(self, m_op_read):
        m_op_read.side_effect = ('key-id', 'secret')
        auth = aws.op_auth('op://Private/aws')
        assert auth.access_key_id == 'key-id'
        assert auth.secret_key == 'secret'
        assert auth.mfa_serial == ''
        assert auth.mfa_code is None

        assert m_op_read.mock_calls == [
            mock.call('op://Private/aws/access-key-id'),
            mock.call('op://Private/aws/secret-access-key'),
        ]


class TestOPSessCreds:
    @patch_obj(aws, 'op_auth')
    @patch_obj(aws, 'sts_session')
    def test_basics(self, m_sts_sess, m_op_auth, tmp_path: Path):
        m_sts_sess.return_value = creds = aws.SessCreds(
            'key-id',
            'sec-key',
            'sess-token',
            utils.utc_now_in(minutes=6),
        )
        assert aws.op_sess_creds('op://env-config-test/aws', 'foo', _cache_dpath=tmp_path) == creds

        # This call should get the creds from the encrypted cache
        assert aws.op_sess_creds('op://env-config-test/aws', 'foo', _cache_dpath=tmp_path) == creds

        # Only called once due to cache
        m_op_auth.assert_called_once_with('op://env-config-test/aws', 'foo')

        # This call should not used the cache value due to the changed MTP arn
        aws.op_sess_creds('op://env-config-test/aws', 'bar', _cache_dpath=tmp_path)
        assert m_op_auth.call_count == 2

    @patch_obj(aws, 'op_auth')
    @patch_obj(aws, 'sts_session')
    def test_expiring_regenerates(self, m_sts_sess, m_op_auth, tmp_path: Path):
        m_sts_sess.return_value = creds = aws.SessCreds(
            'key-id',
            'sec-key',
            'sess-token',
            utils.utc_now_in(minutes=4),
        )
        # Caches the credentials
        assert aws.op_sess_creds('op://env-config-test/aws', 'foo', _cache_dpath=tmp_path)

        # Retrieves them but since they expire within 5 minutes, regenerates them
        assert aws.op_sess_creds('op://env-config-test/aws', 'foo', _cache_dpath=tmp_path) == creds

        assert m_op_auth.call_count == 2
