from functools import cache
import logging
from os import environ
import shlex
import subprocess

from dynamic_yaml.yaml_wrappers import YamlDict

from . import config


log = logging.getLogger(__name__)


class UserError(RuntimeError):
    pass


def sub_run(*args, **kwargs):
    kwargs.setdefault('check', True)
    return subprocess.run(args, **kwargs)


class OPResolver:
    @staticmethod
    def use(val: str) -> bool:
        return val and val.startswith('op://')

    @staticmethod
    def convert(uri: str) -> bool:
        result = sub_run('op', 'read', '-n', uri, capture_output=True)
        return result.stdout.decode('utf-8')


class AWSVaultResolver:
    duration = environ.get('ENV_CONFIG_AWS_VAULT_DURATION', '1h')
    prompt = environ.get('ENV_CONFIG_AWS_VAULT_PROMPT', 'zenity')

    @staticmethod
    def use(val: str) -> bool:
        return val and val.startswith('aws-vault://')

    @classmethod
    def convert(cls, uri: str) -> bool:
        vault_profile, envvar_name = uri.replace('aws-vault://', '', 1).split('/')
        return cls.vault_env(vault_profile)[envvar_name]

    @classmethod
    @cache
    def vault_env(cls, profile):
        # Custom environment for aws-vault exec because it warns against nesting sessions.
        env = environ.copy()
        for varname in config.AWS_VAULT_VARS:
            if varname in env:
                del env[varname]

        try:
            result = sub_run(
                'aws-vault',
                'exec',
                profile,
                '--duration',
                cls.duration,
                '--prompt',
                cls.prompt,
                '--',
                'printenv',
                *config.AWS_VAULT_VARS,
                capture_output=True,
                env=env,
            )
        except subprocess.CalledProcessError as e:
            log.error(f'stdout: {e.stdout}')
            log.error(f'stderr: {e.stderr}')
            raise

        values = result.stdout.decode('utf-8').strip().splitlines()
        return {key: values[i] for i, key in enumerate(config.AWS_VAULT_VARS)}


class EnvConfig:
    resolvers = (OPResolver, AWSVaultResolver)

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

    def resolve(self, selected_names: list[str]):
        """
        Return all env name to value mappings in given selected names after resolving includes and
        any "special" config values that need processing/resolving.
        """
        env_vars: dict[str, str] = self.select(selected_names)

        for name in env_vars:
            value = env_vars[name]
            for resolver in self.resolvers:
                if resolver.use(value):
                    env_vars[name] = resolver.convert(value)

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
