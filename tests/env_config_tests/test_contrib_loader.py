import pytest

from env_config import core
from env_config.contrib import EnvVar, Loader
from env_config_tests.libs.testing import patch_obj


class ExampleVars(Loader):
    gh_token = EnvVar('github.EC_GITHUB_TOKEN')
    foo_secret_prod = EnvVar('foo-prod.EC_FOO_SECRET')
    plain = EnvVar('misc.EC_PLAIN_VALUE')
    group_value = EnvVar('team.EC_GROUP_VALUE')
    shared_value = EnvVar('shared.EC_SHARED_VALUE')


class DuplicateVars(Loader):
    foo_secret = EnvVar('EC_FOO_SECRET')


class SecretVars(Loader):
    deploy_key = EnvVar('foo-prod.EC_DEPLOY_KEY')


class PromptVars(Loader):
    prompt_key = EnvVar('prompt-source.EC_PROMPT_VALUE')


class MissingPrefixVars(Loader):
    missing_value = EnvVar('missing.EC_MISSING_VALUE')


class DuplicateGroupVars(Loader):
    dup_value = EnvVar('dup-team.EC_DUP_VALUE')


class BrokenGroupVars(Loader):
    broken_value = EnvVar('broken-team.EC_ANY_VALUE')


class MissingProfileKeyVars(Loader):
    missing_key = EnvVar('github.NON_EXISTENT')


class ChildVars(ExampleVars):
    extra_plain = EnvVar('misc.EC_PLAIN_VALUE')


class OverrideChildVars(ExampleVars):
    gh_token = EnvVar('misc.EC_PLAIN_VALUE')


class TestLoader:
    @pytest.fixture(autouse=True)
    def fixture_config(self, tmp_path):
        self.project_dpath = tmp_path / 'project'
        self.work_dpath = self.project_dpath / 'src' / 'app'
        self.work_dpath.mkdir(parents=True)
        config_fpath = self.project_dpath / 'env-config.yaml'
        config_fpath.write_text(
            """
profile:
  github:
    EC_GITHUB_TOKEN: 'gh-token'
  foo-prod:
    EC_FOO_SECRET: 'bar'
    EC_DEPLOY_KEY: 'op://private/deploy/key'
  foo-beta:
    EC_FOO_SECRET: 'baz'
  misc:
    EC_PLAIN_VALUE: 'plain-text'
  grouped-source:
    EC_GROUP_VALUE: 'from-group'
    EC_SHARED_VALUE: 'from-group'
  shared:
    EC_SHARED_VALUE: 'from-prefix-profile'
  dup-a:
    EC_DUP_VALUE: 'a'
  dup-b:
    EC_DUP_VALUE: 'b'
  prompt-source:
    EC_PROMPT_VALUE: 'prompt://enter-value'
group:
  team:
    - grouped-source
  shared:
    - grouped-source
  dup-team:
    - dup-a
    - dup-b
  broken-team:
    - missing-profile
""".strip(),
        )

    def test_load_from_project_path(self):
        env_vars = ExampleVars.load(self.work_dpath)

        assert isinstance(env_vars.gh_token, EnvVar)
        assert env_vars.gh_token.env_key == 'EC_GITHUB_TOKEN'
        assert env_vars.foo_secret_prod.value == 'bar'
        assert env_vars.plain.value == 'plain-text'
        assert env_vars.group_value.value == 'from-group'
        assert env_vars.shared_value.value == 'from-prefix-profile'

    def test_envvar_without_prefix_uses_full_ident(self):
        assert EnvVar('FOO').env_key == 'FOO'

    def test_load_fails_for_duplicate_without_prefix(self):
        with pytest.raises(core.UserError) as info:
            DuplicateVars.load(self.work_dpath)

        assert str(info.value) == (
            "Env var 'EC_FOO_SECRET' is defined multiple times in all profiles: foo-beta, "
            'foo-prod. Use a profile or group name prefix to select the desired value.'
        )

    @patch_obj(core.OPResolver, 'convert', return_value='resolved-secret')
    def test_load_uses_core_resolvers_for_op_values(self, m_convert):
        env_vars = SecretVars.load(self.work_dpath)

        assert env_vars.deploy_key.value == 'resolved-secret'
        m_convert.assert_called_once_with('EC_DEPLOY_KEY', 'op://private/deploy/key')

    @patch_obj(core.utils, 'zenity_secret', return_value='prompt-secret')
    def test_load_uses_core_resolvers_for_prompt_values(self, m_zenity_secret):
        env_vars = PromptVars.load(self.work_dpath)

        assert env_vars.prompt_key.value == 'prompt-secret'
        m_zenity_secret.assert_called_once_with('EC_PROMPT_VALUE')

    def test_load_fails_for_missing_prefix(self):
        with pytest.raises(core.UserError) as info:
            MissingPrefixVars.load(self.work_dpath)

        assert str(info.value) == (
            "Prefix 'missing' not found as a profile or group for 'EC_MISSING_VALUE'"
        )

    def test_load_fails_for_duplicate_key_in_group(self):
        with pytest.raises(core.UserError) as info:
            DuplicateGroupVars.load(self.work_dpath)

        assert str(info.value) == (
            "Env var 'EC_DUP_VALUE' is defined multiple times in group 'dup-team': dup-a, dup-b. "
            'Use a profile or group name prefix to select the desired value.'
        )

    def test_load_fails_for_group_with_missing_profile(self):
        with pytest.raises(core.UserError) as info:
            BrokenGroupVars.load(self.work_dpath)

        assert str(info.value) == "Group 'broken-team' references missing profile 'missing-profile'"

    def test_load_fails_for_missing_key_in_existing_profile(self):
        with pytest.raises(core.UserError) as info:
            MissingProfileKeyVars.load(self.work_dpath)

        assert str(info.value) == "Env var 'NON_EXISTENT' not found in profile 'github'"

    def test_load_supports_inherited_env_vars(self):
        env_vars = ChildVars.load(self.work_dpath)

        assert env_vars.gh_token.value == 'gh-token'
        assert env_vars.extra_plain.value == 'plain-text'

    def test_declared_env_var_names_dedupes_overrides(self):
        assert OverrideChildVars.declared_env_var_names().count('gh_token') == 1

        env_vars = OverrideChildVars.load(self.work_dpath)
        assert env_vars.gh_token.value == 'plain-text'

    def test_value_requires_loader(self):
        with pytest.raises(core.UserError) as info:
            _ = EnvVar('FOO').value

        assert str(info.value) == 'EnvVar must be bound to a Loader before reading its value'
