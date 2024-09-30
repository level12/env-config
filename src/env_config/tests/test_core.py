from pathlib import Path
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
