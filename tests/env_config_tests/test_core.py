from pathlib import Path
from unittest import mock

from env_config import config, core
from env_config_tests.libs.testing import patch_obj


configs = Path(__file__).parent / 'configs'


def load(fname) -> core.EnvConfig:
    conf = config.load(configs / fname)
    return core.EnvConfig(conf)


class TestEnvConfig:
    def test_select_profiles(self):
        ec = load('basics.yaml')
        assert ec.select_profiles(['tng']) == {
            'tng': {
                'PICARD': 'captain',
                'RIKER': 'number1',
            },
        }
        assert ec.select_profiles(['ds9']) == {
            'ds9': {
                'SISKO': 'depends on season',
            },
        }

        assert ec.select_profiles(['tng', 'ds9']) == {
            'ds9': {
                'SISKO': 'depends on season',
            },
            'tng': {
                'PICARD': 'captain',
                'RIKER': 'number1',
            },
        }

    def test_groups(self):
        ec = load('basics.yaml')
        assert ec.select_groups(['starfleet']) == {
            'ds9': {
                'SISKO': 'depends on season',
            },
            'tng': {
                'PICARD': 'captain',
                'RIKER': 'number1',
            },
        }
        assert ec.select_groups(['ds9']) == {}
        assert ec.select_groups(['tng']) == {}
        assert ec.select_groups(['foo']) == {}

    def test_select(self):
        ec = load('basics.yaml')
        assert ec.select(['tng']) == {
            'PICARD': 'captain',
            'RIKER': 'number1',
        }
        assert ec.select(['ds9']) == {
            'SISKO': 'depends on season',
        }

        assert ec.select(['tng', 'ds9']) == {
            'SISKO': 'depends on season',
            'PICARD': 'captain',
            'RIKER': 'number1',
        }

        assert ec.select(['starfleet']) == {
            'SISKO': 'depends on season',
            'PICARD': 'captain',
            'RIKER': 'number1',
        }

    def test_present_env_vars(self):
        ec = load('basics.yaml')
        with mock.patch.dict(core.environ, SISKO='foo'):
            assert ec.present_env_vars() == {
                'SISKO',
            }

    @patch_obj(core.OPResolver, attribute='convert', return_value='foo secret')
    def test_resolve_1pass(self, m_convert):
        ec = load('1pass.yaml')
        assert ec.resolve(['tng']) == {
            'PICARD': 'captain',
            'RIKER': 'foo secret',
        }

    def test_resolve_yaml_bool(self):
        ec = load('basics.yaml')

        assert ec.resolve(['aws-cli']) == {
            'AWS_IGNORE_CONFIGURED_ENDPOINT_URLS': 'true',
        }


class TestOPResolver:
    @patch_obj(core.utils, 'op_read', return_value='Q')
    def test_op_call(self, m_op_read):
        assert core.OPResolver.convert('foo-env-name', 'op://Private/god-like-misanthrope') == 'Q'

        m_op_read.assert_called_once_with('op://Private/god-like-misanthrope')

    @patch_obj(core.utils, 'op_read')
    def test_empty_env_override_is_literal(self, m_op_read):
        with mock.patch.dict(core.environ, {'CORE_TEST_DEPLOY_KEY': ''}, clear=True):
            assert core.OPResolver.convert('CORE_TEST_DEPLOY_KEY', 'op://private/deploy/key') == ''

        m_op_read.assert_not_called()

    @patch_obj(core.utils, 'op_read')
    def test_env_override_beats_systemd_credentials(self, m_op_read, tmp_path):
        creds_dpath = tmp_path / 'creds'
        creds_dpath.mkdir()
        (creds_dpath / 'CORE_TEST_DEPLOY_KEY').write_text('from-creds')

        with mock.patch.dict(
            core.environ,
            {
                'CORE_TEST_DEPLOY_KEY': 'from-env',
                'CREDENTIALS_DIRECTORY': str(creds_dpath),
            },
            clear=True,
        ):
            assert core.OPResolver.convert('CORE_TEST_DEPLOY_KEY', 'op://private/deploy/key') == (
                'from-env'
            )

        m_op_read.assert_not_called()

    @patch_obj(core.utils, 'op_read')
    def test_env_override(self, m_op_read):
        with mock.patch.dict(core.environ, {'CORE_TEST_DEPLOY_KEY': 'from-env'}, clear=True):
            assert (
                core.OPResolver.convert('CORE_TEST_DEPLOY_KEY', 'op://private/deploy/key')
                == 'from-env'
            )

        m_op_read.assert_not_called()

    @patch_obj(core.utils, 'op_read')
    def test_systemd_credentials(self, m_op_read, tmp_path):
        creds_dpath = tmp_path / 'creds'
        creds_dpath.mkdir()
        (creds_dpath / 'CORE_TEST_DEPLOY_KEY').write_text('from-creds')

        with mock.patch.dict(core.environ, {'CREDENTIALS_DIRECTORY': str(creds_dpath)}, clear=True):
            assert core.OPResolver.convert('CORE_TEST_DEPLOY_KEY', 'op://private/deploy/key') == (
                'from-creds'
            )

        m_op_read.assert_not_called()

    @patch_obj(core.utils, 'op_read', return_value='from-op')
    def test_missing_systemd_credential_falls_back_to_uri(self, m_op_read, tmp_path):
        creds_dpath = tmp_path / 'creds'
        creds_dpath.mkdir()

        with mock.patch.dict(core.environ, {'CREDENTIALS_DIRECTORY': str(creds_dpath)}, clear=True):
            assert core.OPResolver.convert('CORE_TEST_DEPLOY_KEY', 'op://private/deploy/key') == (
                'from-op'
            )

        m_op_read.assert_called_once_with('op://private/deploy/key')

    @patch_obj(core.utils, 'op_read', return_value='from-op')
    def test_override_ref(self, m_op_read):
        with mock.patch.dict(
            core.environ,
            {'CORE_TEST_DEPLOY_KEY_1PASS_REF': 'op://override/deploy/key'},
            clear=True,
        ):
            assert core.OPResolver.convert('CORE_TEST_DEPLOY_KEY', 'op://private/deploy/key') == (
                'from-op'
            )

        m_op_read.assert_called_once_with('op://override/deploy/key')

    @patch_obj(core.utils, 'op_read', return_value='from-op')
    def test_empty_override_ref_is_literal(self, m_op_read):
        with mock.patch.dict(core.environ, {'CORE_TEST_DEPLOY_KEY_1PASS_REF': ''}, clear=True):
            assert core.OPResolver.convert('CORE_TEST_DEPLOY_KEY', 'op://private/deploy/key') == (
                'from-op'
            )

        m_op_read.assert_called_once_with('')
