from pathlib import Path
import subprocess
from unittest import mock

from env_config import config, core


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

    @mock.patch.object(core.OPResolver, attribute='convert', return_value='foo secret')
    def test_resolve_1pass(self, m_convert):
        ec = load('1pass.yaml')
        assert ec.resolve(['tng']) == {
            'PICARD': 'captain',
            'RIKER': 'foo secret',
        }

    @mock.patch.object(core, 'sub_run')
    def test_resolve_aws_vault(self, m_sub_run):
        stdout = b'key-id\naccess-key\nsess-token\nsec-token\nvault\nexpires'
        m_sub_run.return_value = subprocess.CompletedProcess((), 0, stdout, b'')

        ec = load('aws.yaml')
        assert ec.resolve(['aws.level12']) == {
            'AWS_ACCESS_KEY_ID': 'key-id',
            'AWS_SECRET_ACCESS_KEY': 'access-key',
            'AWS_SESSION_TOKEN': 'sess-token',
            'AWS_SECURITY_TOKEN': 'sec-token',
            'AWS_VAULT': 'vault',
            'AWS_SESSION_EXPIRATION': 'expires',
        }

        # called_once is important as it makes sure we are caching the result
        m_sub_run.assert_called_once_with(
            'aws-vault',
            'exec',
            'level12',
            '--duration',
            '1h',
            '--prompt',
            'zenity',
            '--',
            'printenv',
            'AWS_ACCESS_KEY_ID',
            'AWS_SECRET_ACCESS_KEY',
            'AWS_SESSION_TOKEN',
            'AWS_SECURITY_TOKEN',
            'AWS_VAULT',
            'AWS_SESSION_EXPIRATION',
            capture_output=True,
            env=mock.ANY,
        )
