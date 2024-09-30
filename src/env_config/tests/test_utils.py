from env_config import utils
from env_config.libs.testing import patch_obj


class TestOPRead:
    @patch_obj(utils, 'sub_run')
    def test_basic(self, m_sub_run):
        m_sub_run.return_value.stdout = 'ds9'
        assert utils.op_read('op://private/runabout') == 'ds9'
        m_sub_run.assert_called_once_with('op', 'read', '-n', 'op://private/runabout', capture=True)

    @patch_obj(utils, 'sub_run')
    def test_with_account(self, m_sub_run):
        m_sub_run.return_value.stdout = 'ds9'
        assert utils.op_read('op://starfleet/private/runabout') == 'ds9'
        m_sub_run.assert_called_once_with(
            'op',
            '--account',
            'starfleet',
            'read',
            '-n',
            'op://private/runabout',
            capture=True,
        )

    @patch_obj(utils, 'sub_run')
    def test_with_spaces(self, m_sub_run):
        m_sub_run.return_value.stdout = 'ds9'
        assert utils.op_read('op://starfleet/private/run about') == 'ds9'
        m_sub_run.assert_called_once_with(
            'op',
            '--account',
            'starfleet',
            'read',
            '-n',
            'op://private/run about',
            capture=True,
        )
