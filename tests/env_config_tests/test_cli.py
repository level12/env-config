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

    runner = CliRunner()
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
        assert result.stdout.strip() == expect_stdout.strip()
        if expect_stderr is not None:
            assert result.stderr.strip() == expect_stderr.strip()

        return result

    def test_fish_basics(self):
        expect_stdout = """
# FISH SOURCE
set -gx _ENV_CONFIG_PROFILES tng
set -gx _ENV_CONFIG_VARS 'PICARD RIKER'
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
set -eg _ENV_CONFIG_VARS
# FISH SOURCE
set -gx _ENV_CONFIG_PROFILES tng
set -gx _ENV_CONFIG_VARS 'PICARD RIKER'
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
            _ENV_CONFIG_PROFILES='tng ds9',
            SISKO='foo',
            RIKER='number2',
        )

        self.check_invoke(
            'basics.yaml',
            'tng',
            '--debug',
            expect_stdout='',
            expect_stderr=expect_stderr,
            _ENV_CONFIG_PROFILES='tng ds9',
            SISKO='foo',
            RIKER='number2',
        )

    def test_switch_does_not_clear_unmanaged_configured_vars(self):
        expect_stdout = """
# FISH SOURCE
set -gx _ENV_CONFIG_PROFILES tng
set -gx _ENV_CONFIG_VARS 'PICARD RIKER'
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
            'tng',
            expect_stdout=expect_stdout,
            expect_stderr=expect_stderr,
            AWS_ACCESS_KEY_ID='from-mise',
            AWS_SECRET_ACCESS_KEY='from-mise',
        )

    def test_switch_clears_configured_vars_when_current_profile_is_stale(self):
        expect_stdout = """
# FISH SOURCE
set -eg AWS_ACCESS_KEY_ID
set -eg AWS_SECRET_ACCESS_KEY
set -eg _ENV_CONFIG_PROFILES
set -eg _ENV_CONFIG_VARS
# FISH SOURCE
set -gx _ENV_CONFIG_PROFILES tng
set -gx _ENV_CONFIG_VARS 'PICARD RIKER'
set -gx PICARD captain
set -gx RIKER number1
"""

        expect_stderr = """
Clearing:
     AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
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
            _ENV_CONFIG_PROFILES='legacy-aws',
            AWS_ACCESS_KEY_ID='from-prev-ec',
            AWS_SECRET_ACCESS_KEY='from-prev-ec',
        )

    def test_switch_clears_vars_removed_from_the_same_profile(self, tmp_path):
        config_fpath = tmp_path / 'env-config.yaml'
        config_fpath.write_text(
            """profile:
  demo:
    FOO: one
""",
        )

        runner = CliRunner()
        first_result = runner.invoke(
            env_config,
            ('--config', config_fpath.as_posix(), '--shell', 'bash', 'demo'),
            catch_exceptions=False,
            auto_envvar_prefix=ENVVAR_PREFIX,
        )

        assert first_result.exit_code == 0, (first_result.stdout, first_result.stderr)
        assert (
            first_result.stdout.strip()
            == """
# BASH SOURCE
export _ENV_CONFIG_PROFILES=demo
export _ENV_CONFIG_VARS=FOO
export FOO=one
""".strip()
        )

        config_fpath.write_text(
            """profile:
  demo:
    BAR: two
""",
        )

        second_result = runner.invoke(
            env_config,
            ('--config', config_fpath.as_posix(), '--shell', 'bash', 'demo'),
            catch_exceptions=False,
            auto_envvar_prefix=ENVVAR_PREFIX,
            env={
                '_ENV_CONFIG_PROFILES': 'demo',
                '_ENV_CONFIG_VARS': 'FOO',
                'FOO': 'one',
            },
        )

        assert second_result.exit_code == 0, (second_result.stdout, second_result.stderr)
        assert (
            second_result.stderr.strip()
            == """
Clearing:
     FOO
Profiles active: demo
Setting:
    BAR: two
""".strip()
        )
        assert (
            second_result.stdout.strip()
            == """
# BASH SOURCE
unset FOO
unset _ENV_CONFIG_PROFILES
unset _ENV_CONFIG_VARS
# BASH SOURCE
export _ENV_CONFIG_PROFILES=demo
export _ENV_CONFIG_VARS=BAR
export BAR=two
""".strip()
        )

    def test_clear_uses_managed_var_list(self):
        expect_stdout = """
# BASH SOURCE
unset FOO
unset _ENV_CONFIG_PROFILES
unset _ENV_CONFIG_VARS
"""

        expect_stderr = """
Clearing:
     FOO
"""

        self.check_invoke(
            'basics.yaml',
            '--clear',
            shell='bash',
            expect_stdout=expect_stdout,
            expect_stderr=expect_stderr,
            _ENV_CONFIG_PROFILES='demo',
            _ENV_CONFIG_VARS='FOO',
            FOO='one',
        )

    def test_clear_unsets_metadata_when_no_managed_vars_are_present(self):
        expect_stdout = """
# BASH SOURCE
unset _ENV_CONFIG_PROFILES
unset _ENV_CONFIG_VARS
"""

        expect_stderr = """
Clearing:
     No configured vars present to clear.
"""

        self.check_invoke(
            'basics.yaml',
            '--clear',
            shell='bash',
            expect_stdout=expect_stdout,
            expect_stderr=expect_stderr,
            _ENV_CONFIG_PROFILES='demo',
            _ENV_CONFIG_VARS='FOO',
        )

    def test_update(self):
        expect_stdout = """
# FISH SOURCE
set -gx _ENV_CONFIG_PROFILES tng
set -gx _ENV_CONFIG_VARS 'PICARD RIKER'
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

    def test_update_appends_profiles(self):
        expect_stdout = """
# FISH SOURCE
set -gx _ENV_CONFIG_PROFILES 'ds9 tng'
set -gx _ENV_CONFIG_VARS 'PICARD RIKER SISKO'
set -gx PICARD captain
set -gx RIKER number1
set -gx SISKO 'depends on season'
"""

        expect_stderr = """
Profiles active: ds9 tng
Setting:
    PICARD: captain
    RIKER: number1
    SISKO: depends on season
"""

        self.check_invoke(
            'basics.yaml',
            'tng',
            '--update',
            expect_stdout=expect_stdout,
            expect_stderr=expect_stderr,
            _ENV_CONFIG_PROFILES='ds9',
        )

    def test_update_refreshes_all_active_profiles(self):
        expect_stdout = """
# FISH SOURCE
set -gx _ENV_CONFIG_PROFILES 'ds9 tng'
set -gx _ENV_CONFIG_VARS 'PICARD RIKER SISKO'
set -gx PICARD captain
set -gx RIKER number1
set -gx SISKO 'depends on season'
"""

        expect_stderr = """
Profiles active: ds9 tng
Setting:
    PICARD: captain
    RIKER: number1
    SISKO: depends on season
"""

        self.check_invoke(
            'basics.yaml',
            'ds9',
            '--update',
            expect_stdout=expect_stdout,
            expect_stderr=expect_stderr,
            _ENV_CONFIG_PROFILES='ds9 tng',
            SISKO='stale',
            RIKER='stale',
        )

    def test_list_profiles(self):
        expect_stdout = """
Profiles:
    tng
    ds9
    aws-cli
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

    def test_invalid_profile_or_group_name_errors(self):
        result = invoke(
            'basics.yaml',
            'tng',
            'foo',
            env={'ENV_CONFIG_SHELL': 'fish'},
            exit_code=2,
        )

        assert result.stdout == ''
        error = result.stderr.strip()
        assert error.startswith('Usage: env-config')
        assert error.endswith('Unknown env-config profile or group: foo')

    def test_bash_exports(self):
        expect_stdout = """
# BASH SOURCE
export _ENV_CONFIG_PROFILES=tng
export _ENV_CONFIG_VARS='PICARD RIKER'
export PICARD=captain
export RIKER=number1
"""

        self.check_invoke(
            'basics.yaml',
            'tng',
            shell='bash',
            expect_stdout=expect_stdout,
        )
