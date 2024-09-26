from pathlib import Path

from click.testing import CliRunner, Result

from env_config.cli import ENVVAR_PREFIX, env_config, env_config_shell


configs = Path(__file__).parent / 'configs'


def invoke_shell(*args, **kwargs) -> Result:
    kwargs.setdefault('catch_exceptions', False)
    runner = CliRunner()
    result = runner.invoke(env_config_shell, args, **kwargs)
    assert result.exit_code == 0
    return result


def invoke(config_fname, *args, exit_code=0, **kwargs) -> Result:
    kwargs.setdefault('catch_exceptions', False)
    kwargs.setdefault('auto_envvar_prefix', ENVVAR_PREFIX)

    config_fpath = configs.joinpath(config_fname).as_posix()
    args = ('--config', config_fpath, *args)

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(env_config, args, **kwargs)

    assert result.exit_code == exit_code, (result.stdout, result.stderr)
    return result


class TestEnvConfigShell:
    def test_fish(self):
        result = invoke_shell('fish')
        assert 'function env-config' in result.stdout


class TestEnvConfig:
    def check_invoke(
        self,
        config_fname,
        *args,
        expect_stdout,
        expect_stderr=None,
        shell='fish',
        exit_code=0,
        **env,
    ):
        if shell is not None:
            env['ENV_CONFIG_SHELL'] = shell

        result = invoke(config_fname, *args, env=env, exit_code=exit_code)
        print(result.stdout, result.stderr)
        assert result.stdout.strip() == expect_stdout.strip()
        if expect_stderr is not None:
            assert result.stderr.strip() == expect_stderr.strip()

        return result

    def test_fish_basics(self):
        expect_stdout = """
# FISH SOURCE
set -gx _ENV_CONFIG_PROFILES tng
set -gx PICARD captain
set -gx RIKER number1
"""

        expect_stderr = """
Clearing:
     No configured vars present to clear.
Profiles active: tng
Setting:
    PICARD: captain
    RIKER: number1
"""

        self.check_invoke(
            'basics.yaml',
            '--shell',
            'fish',
            'tng',
            expect_stdout=expect_stdout,
            expect_stderr=expect_stderr,
            # shell=None ensures the option from the cli is being used
            shell=None,
        )

    def test_clear_existing_and_debug(self):
        expect_stdout = """
# FISH SOURCE
set -eg RIKER
set -eg SISKO
set -eg _ENV_CONFIG_PROFILES
# FISH SOURCE
set -gx _ENV_CONFIG_PROFILES tng
set -gx PICARD captain
set -gx RIKER number1
"""

        expect_stderr = """
Clearing:
     RIKER, SISKO
Profiles active: tng
Setting:
    PICARD: captain
    RIKER: number1
"""

        self.check_invoke(
            'basics.yaml',
            'tng',
            expect_stdout=expect_stdout,
            expect_stderr=expect_stderr,
            SISKO='foo',
            RIKER='number2',
        )

        self.check_invoke(
            'basics.yaml',
            'tng',
            '--debug',
            expect_stdout='',
            expect_stderr=expect_stderr,
            SISKO='foo',
            RIKER='number2',
        )

    def test_update(self):
        expect_stdout = """
# FISH SOURCE
set -gx _ENV_CONFIG_PROFILES tng
set -gx PICARD captain
set -gx RIKER number1
"""

        expect_stderr = """
Profiles active: tng
Setting:
    PICARD: captain
    RIKER: number1
"""

        self.check_invoke(
            'basics.yaml',
            'tng',
            '--update',
            expect_stdout=expect_stdout,
            expect_stderr=expect_stderr,
            SISKO='foo',
            RIKER='number2',
        )

    def test_list_profiles(self):
        expect_stdout = """
Profiles:
    tng
    ds9
Groups:
    starfleet
"""

        self.check_invoke(
            'basics.yaml',
            '--list',
            expect_stdout=expect_stdout,
            expect_stderr='',
        )

    def test_show_profiles_in_use(self):
        self.check_invoke(
            'basics.yaml',
            expect_stdout='',
            expect_stderr='No env-config profiles currently in use.',
        )

        expect_stderr = """
Profiles active: tng ds9
Active profile(s) configuration:
    PICARD: captain
    RIKER: number1
    SISKO: depends on season
"""

        self.check_invoke(
            'basics.yaml',
            expect_stdout='',
            expect_stderr=expect_stderr,
            _ENV_CONFIG_PROFILES='tng ds9',
        )

    def test_user_error_doesnt_raise(self):
        result = self.check_invoke(
            'fake.not-yaml',
            exit_code=2,
            expect_stdout='',
        )
        error = result.stderr.strip()
        assert error.startswith('Usage: env-config')
        assert error.endswith('/fake.not-yaml should be a directory or .yaml file')

    def test_bash_exports(self):
        expect_stdout = """
# BASH SOURCE
export _ENV_CONFIG_PROFILES=tng
export PICARD=captain
export RIKER=number1
"""

        self.check_invoke(
            'basics.yaml',
            'tng',
            shell='bash',
            expect_stdout=expect_stdout,
        )
