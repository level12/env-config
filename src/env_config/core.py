import logging
from os import environ
from pathlib import Path
import shlex

from dynamic_yaml.yaml_wrappers import YamlDict

from . import utils


log = logging.getLogger(__name__)


class UserError(RuntimeError):
    pass


class Resolver:
    scheme: str

    @classmethod
    def use(cls, val: str) -> bool:
        return bool(val) and val.startswith(cls.scheme)

    @classmethod
    def convert(cls, env_name: str, uri: str) -> str:
        raise NotImplementedError


class OPResolver(Resolver):
    scheme = 'op://'

    @classmethod
    def convert(cls, env_name: str, uri: str) -> str:
        # Treat operator-provided env overrides literally, including the empty string.
        if env_name in environ:
            return environ[env_name]

        if systemd_creds_dir := environ.get('CREDENTIALS_DIRECTORY'):
            creds_fpath = Path(systemd_creds_dir) / env_name
            if creds_fpath.exists():
                # Don't strip whitespace.  Assume competent operators are not adding whitespace
                # to their creds accidently.  Even if that proves false, this isn't the place
                # to fix it.
                return creds_fpath.read_text()

        # Treat the explicit override ref literally too, including the empty string.
        uri = environ.get(f'{env_name}_1PASS_REF', uri)
        return utils.op_read(uri)


class PromptResolver(Resolver):
    scheme = 'prompt://'

    @classmethod
    def convert(cls, env_name: str, uri: str) -> str:
        return utils.zenity_secret(env_name)


class EnvConfig:
    resolvers = (OPResolver, PromptResolver)

    def __init__(self, config: YamlDict):
        self.config: YamlDict = config
        self.stderr = []
        self.stdout = []

    def select_profiles(self, prof_names: list[str] | None = None) -> dict[str, dict]:
        """Return configs that represent env var name to value mappings"""
        prof_names = set(prof_names)
        return {
            prof_name: config
            for prof_name, config in self.config.profile.items()
            if prof_name in prof_names
        }

    def present_env_vars(self) -> set[str]:
        """Return all env var names used in any config active in current environment"""
        return {
            var_name
            for var_map in self.config.profile.values()
            for var_name in var_map
            if var_name in environ
        }

    def select_groups(self, group_names: list[str]) -> dict[str, dict]:
        """Select profiles included in the given groups"""
        group_names = set(group_names)
        return {
            # For each profile name included, use its name and config
            included_prof_name: self.config.profile[included_prof_name]
            # Get configs requested that represent other included figs
            for group_name, includes in self.config.group.items()
            if group_name in group_names
            # Includes is a list of profile names to include, flatten it
            for included_prof_name in includes
        }

    def select(cls, selected_names: list[str]) -> dict[str, str]:
        """
        Return all env name to value mappings in given selection names after resolving includes.
        """
        merged = cls.select_groups(selected_names) | cls.select_profiles(selected_names)
        return {
            env_name: env_value
            for env_map in merged.values()
            for env_name, env_value in env_map.items()
        }

    @classmethod
    def resolve_value(cls, env_name: str, value: str) -> str:
        """Apply the first matching resolver or return the raw value unchanged."""
        for resolver in cls.resolvers:
            if resolver.use(value):
                return resolver.convert(env_name, value)

        return value

    def resolve(self, selected_names: list[str]):
        """
        Return all env name to value mappings in given selected names after resolving includes and
        any "special" config values that need processing/resolving.
        """
        env_vars: dict[str, str] = self.select(selected_names)

        for name in env_vars:
            env_vars[name] = self.resolve_value(name, env_vars[name])

        return env_vars


class FishEnvConfig(EnvConfig):
    def clear_present_env_vars(self):
        var_names = sorted(self.present_env_vars())
        if not var_names:
            return

        print('# FISH SOURCE')
        for var_name in var_names:
            print('set', '-eg', shlex.quote(var_name))

        print('set', '-eg', '_ENV_CONFIG_PROFILES')

    def set(self, selected_names: list[str]):
        print('# FISH SOURCE')
        print('set', '-gx', '_ENV_CONFIG_PROFILES', shlex.quote(' '.join(selected_names)))
        for var, value in self.resolve(selected_names).items():
            # Fish puts sourced variables in their own local scope by default so use -g to get them
            # to the scope of the sourcing shell and -x to export them.
            print('set', '-gx', shlex.quote(var), shlex.quote(value))


class BashEnvConfig(EnvConfig):
    def clear_present_env_vars(self):
        var_names = sorted(self.present_env_vars())
        if not var_names:
            return

        print('# BASH SOURCE')
        for var_name in var_names:
            print('unset', shlex.quote(var_name))

        print('unset', '_ENV_CONFIG_PROFILES')

    def set(self, selected_names: list[str]):
        print('# BASH SOURCE')
        print('export', '_ENV_CONFIG_PROFILES=' + shlex.quote(' '.join(selected_names)))
        for var, value in self.resolve(selected_names).items():
            print('export', shlex.quote(var) + '=' + shlex.quote(value))
