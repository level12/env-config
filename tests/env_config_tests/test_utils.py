import sys

import pytest

from env_config import utils
from env_config_tests.libs.testing import patch_obj


class TestOPRead:
    @patch_obj(utils, 'sub_run')
    def test_basic(self, m_sub_run):
        m_sub_run.return_value.stdout = 'ds9'
        assert utils.op_read('op://private/runabout/phasers') == 'ds9'
        m_sub_run.assert_called_once_with(
            'op',
            'read',
            '-n',
            'op://private/runabout/phasers',
            capture=True,
        )

    @patch_obj(utils, 'sub_run')
    def test_with_account(self, m_sub_run):
        m_sub_run.return_value.stdout = 'ds9'
        assert utils.op_read('op://starfleet/private/runabout/phasers') == 'ds9'
        m_sub_run.assert_called_once_with(
            'op',
            '--account',
            'starfleet',
            'read',
            '-n',
            'op://private/runabout/phasers',
            capture=True,
        )

    @patch_obj(utils, 'sub_run')
    def test_with_spaces(self, m_sub_run):
        m_sub_run.return_value.stdout = 'ds9'
        assert utils.op_read('op://starfleet/private/run about/phasers') == 'ds9'
        m_sub_run.assert_called_once_with(
            'op',
            '--account',
            'starfleet',
            'read',
            '-n',
            'op://private/run about/phasers',
            capture=True,
        )


class TestMachineIdent:
    @patch_obj(utils.platform, 'system', return_value='Darwin')
    @patch_obj(utils, 'machine_ident_mac', return_value='mac-id')
    def test_calls_mac_impl_on_macos(self, m_machine_ident_mac, m_platform_system):
        assert utils.machine_ident() == 'mac-id'

        m_platform_system.assert_called_once_with()
        m_machine_ident_mac.assert_called_once_with()

    @pytest.mark.skipif(sys.platform != 'darwin', reason='macOS only')
    def test_mac_impl_real(self):
        value = utils.machine_ident_mac()
        assert isinstance(value, str)
        assert value
