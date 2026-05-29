from collections.abc import Mapping
from functools import cached_property
from pathlib import Path
from typing import Self

from .. import config, core


class EnvVar:
    def __init__(self, ident: str, loader: 'Loader | None' = None) -> None:
        self.ident = ident
        self.loader = loader

    @cached_property
    def ident_parts(self) -> tuple[str | None, str]:
        prefix, has_prefix, env_key = self.ident.partition('.')
        if not has_prefix:
            return None, self.ident

        return prefix, env_key

    @cached_property
    def prefix(self) -> str | None:
        return self.ident_parts[0]

    @cached_property
    def env_key(self) -> str:
        return self.ident_parts[1]

    @cached_property
    def value(self) -> str:
        if self.loader is None:
            raise core.UserError('EnvVar must be bound to a Loader before reading its value')

        return core.EnvConfig.resolve_value(self.env_key, self.loader.raw_value(self))


class Loader:
    def __init__(self, start_at: Path) -> None:
        self.config = config.load(start_at)
        for attr_name in self.declared_env_var_names():
            env_var = getattr(type(self), attr_name)
            setattr(self, attr_name, EnvVar(env_var.ident, loader=self))

    @classmethod
    def load(cls, start_at: Path) -> Self:
        """Create a loader and eagerly resolve all declared environment variables."""
        loader = cls(start_at)

        # NOTE: If a user does not want eager value checks, instantiate their Loader subclass
        # directly with start_at instead of calling .load().
        for attr_name in loader.declared_env_var_names():
            _ = getattr(loader, attr_name).value

        return loader

    @classmethod
    def declared_env_var_names(cls) -> list[str]:
        """Return declared EnvVar attribute names with child-class overrides winning."""
        env_var_names = []
        for base in reversed(cls.__mro__):
            for attr_name, attr_value in base.__dict__.items():
                if isinstance(attr_value, EnvVar):
                    if attr_name in env_var_names:
                        env_var_names.remove(attr_name)

                    env_var_names.append(attr_name)

        return env_var_names

    def raw_value(self, env_var: EnvVar) -> str:
        """Return the unresolved config value for the given EnvVar."""
        if env_var.prefix:
            return self.raw_value_from_prefix(env_var.prefix, env_var.env_key)

        return self.raw_value_from_env_key(env_var.env_key)

    def raw_value_from_prefix(self, prefix: str, env_key: str) -> str:
        """Return the unresolved value for an env key within the given prefix."""
        if prefix in self.config.profile:
            return self.raw_value_from_profile(prefix, env_key)

        if prefix in self.config.group:
            return self.raw_value_from_group(prefix, env_key)

        raise core.UserError(f'Prefix {prefix!r} not found as a profile or group for {env_key!r}')

    def raw_value_from_profile(self, profile_name: str, env_key: str) -> str:
        """Return the unresolved value for an env key from a single profile."""
        profile = self.config.profile[profile_name]
        if env_key not in profile:
            raise core.UserError(f'Env var {env_key!r} not found in profile {profile_name!r}')

        return profile[env_key]

    def raw_value_from_group(self, group_name: str, env_key: str) -> str:
        """Return the unresolved value for an env key selected from a group."""
        profiles = self.config.group.get(group_name)
        if profiles is None:
            raise core.UserError(f'Group {group_name!r} not found for {env_key!r}')

        env_maps = {}
        for profile_name in profiles:
            if profile_name not in self.config.profile:
                raise core.UserError(
                    f'Group {group_name!r} references missing profile {profile_name!r}',
                )

            env_maps[profile_name] = self.config.profile[profile_name]

        return self.raw_value_from_env_maps(env_maps, env_key, scope=f'group {group_name!r}')

    def raw_value_from_env_key(self, env_key: str) -> str:
        """Return the unresolved value for an unprefixed env key across all profiles."""
        return self.raw_value_from_env_maps(self.config.profile, env_key, scope='all profiles')

    def raw_value_from_env_maps(
        self,
        env_maps: Mapping[str, Mapping[str, str]],
        env_key: str,
        *,
        scope: str,
    ) -> str:
        """Return a single unresolved env value from the provided mappings."""
        matches = [name for name, env_map in env_maps.items() if env_key in env_map]
        if not matches:
            raise core.UserError(f'Env var {env_key!r} not found in {scope}')

        if len(matches) > 1:
            names = ', '.join(sorted(matches))
            raise core.UserError(
                f'Env var {env_key!r} is defined multiple times in {scope}: {names}. '
                'Use a profile or group name prefix to select the desired value.',
            )

        return env_maps[matches[0]][env_key]
