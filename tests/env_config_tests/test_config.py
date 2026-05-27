from pathlib import Path
from unittest import mock

import pytest

from env_config import config, core


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

    def test_no_config(self):
        with pytest.raises(core.UserError) as info:
            config.load(Path('/tmp'))

        assert str(info.value) == 'No env-config.yaml in /tmp or parents'

    def test_invalid_suffix(self):
        with pytest.raises(core.UserError) as info:
            config.load(Path('/tmp/fake.py'))

        assert str(info.value) == '/tmp/fake.py should be a directory or .yaml file'
