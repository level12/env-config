import logging
from os import environ
from pathlib import Path
import shlex

from dynamic_yaml.yaml_wrappers import YamlDict

from . import utils


log = logging.getLogger(__name__)
PROFILES_ENVVAR = '_ENV_CONFIG_PROFILES'
MANAGED_VARS_ENVVAR = '_ENV_CONFIG_VARS'


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

    def known_names(self) -> set[str]:
        return set(self.config.profile) | set(self.config.group)

    def configured_env_var_names(self) -> set[str]:
        return {var_name for var_map in self.config.profile.values() for var_name in var_map}

    def managed_env_var_names(self) -> set[str]:
        return set(environ.get(MANAGED_VARS_ENVVAR, '').strip().split())

    def selected_configs(self, selected_names: list[str]) -> dict[str, dict]:
        return self.select_groups(selected_names) | self.select_profiles(selected_names)

    def selected_env_var_names(self, selected_names: list[str]) -> set[str]:
        known_names = self.known_names()
        if any(name not in known_names for name in selected_names):
            return self.configured_env_var_names()

        return {
            env_name
            for env_map in self.selected_configs(selected_names).values()
            for env_name in env_map
        }

    def present_env_vars(self, selected_names: list[str] | None = None) -> set[str]:
        """Return present env vars, preferring the remembered managed-var list when available."""
        env_var_names = self.managed_env_var_names()
        if not env_var_names:
            env_var_names = (
                self.selected_env_var_names(selected_names)
                if selected_names is not None
                else self.configured_env_var_names()
            )

        return {var_name for var_name in env_var_names if var_name in environ}

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

    def validate_selected_names(self, selected_names: list[str]) -> None:
        known_names = self.known_names()
        for name in selected_names:
            if name not in known_names:
                raise UserError(f'Unknown env-config profile or group: {name}')

    def selected_env_maps_in_order(self, selected_names: list[str]) -> list[dict[str, str | bool]]:
        """Return selected env maps in CLI order.

        Profile tokens win over same-name groups.
        """
        env_maps: list[dict[str, str | bool]] = []

        for name in selected_names:
            if name in self.config.profile:
                env_maps.append(self.config.profile[name])
                continue

            for included_prof_name in self.config.group[name]:
                if included_prof_name not in self.config.profile:
                    raise UserError(
                        f'Group {name!r} references missing profile {included_prof_name!r}',
                    )

                env_maps.append(self.config.profile[included_prof_name])

        return env_maps

    def select(self, selected_names: list[str]) -> dict[str, str]:
        """
        Return all env name to value mappings in given selection names after resolving includes.
        """
        merged = self.selected_configs(selected_names)
        return {
            env_name: env_value
            for env_map in merged.values()
            for env_name, env_value in env_map.items()
        }

    def select_in_order(self, selected_names: list[str]) -> dict[str, str | bool]:
        merged: dict[str, str | bool] = {}

        for env_map in self.selected_env_maps_in_order(selected_names):
            merged.update(env_map)

        return merged

    @classmethod
    def resolve_value(cls, env_name: str, value: str | bool) -> str:
        """Apply the first matching resolver or return the raw value unchanged."""
        if isinstance(value, bool):
            return str(value).lower()

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

    def resolve_in_order(self, selected_names: list[str]) -> dict[str, str]:
        env_vars = self.select_in_order(selected_names)

        for name in env_vars:
            env_vars[name] = self.resolve_value(name, env_vars[name])

        return env_vars


class FishEnvConfig(EnvConfig):
    def clear_present_env_vars(
        self,
        selected_names: list[str] | None = None,
        *,
        clear_metadata: bool = False,
    ):
        var_names = sorted(self.present_env_vars(selected_names))
        if not var_names and not clear_metadata:
            return

        print('# FISH SOURCE')
        for var_name in var_names:
            print('set', '-eg', shlex.quote(var_name))

        print('set', '-eg', PROFILES_ENVVAR)
        print('set', '-eg', MANAGED_VARS_ENVVAR)

    def set(self, selected_names: list[str], *, active_names: list[str] | None = None):
        active_names = active_names or selected_names
        env_vars = self.resolve(selected_names)

        print('# FISH SOURCE')
        print('set', '-gx', PROFILES_ENVVAR, shlex.quote(' '.join(active_names)))
        print('set', '-gx', MANAGED_VARS_ENVVAR, shlex.quote(' '.join(sorted(env_vars))))
        for var, value in env_vars.items():
            # Fish puts sourced variables in their own local scope by default so use -g to get them
            # to the scope of the sourcing shell and -x to export them.
            print('set', '-gx', shlex.quote(var), shlex.quote(value))


class BashEnvConfig(EnvConfig):
    def clear_present_env_vars(
        self,
        selected_names: list[str] | None = None,
        *,
        clear_metadata: bool = False,
    ):
        var_names = sorted(self.present_env_vars(selected_names))
        if not var_names and not clear_metadata:
            return

        print('# BASH SOURCE')
        for var_name in var_names:
            print('unset', shlex.quote(var_name))

        print('unset', PROFILES_ENVVAR)
        print('unset', MANAGED_VARS_ENVVAR)

    def set(self, selected_names: list[str], *, active_names: list[str] | None = None):
        active_names = active_names or selected_names
        env_vars = self.resolve(selected_names)

        print('# BASH SOURCE')
        print('export', PROFILES_ENVVAR + '=' + shlex.quote(' '.join(active_names)))
        print('export', MANAGED_VARS_ENVVAR + '=' + shlex.quote(' '.join(sorted(env_vars))))
        for var, value in env_vars.items():
            print('export', shlex.quote(var) + '=' + shlex.quote(value))
