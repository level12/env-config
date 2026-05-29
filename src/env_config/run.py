from dataclasses import dataclass
from os import environ
from pathlib import Path
import subprocess
from typing import Self

import click

from . import config
from .core import MANAGED_VARS_ENVVAR, PROFILES_ENVVAR, EnvConfig


@dataclass
class RunRequest:
    profiles: list[str]
    command_argv: list[str]

    @classmethod
    def parse(cls, args: tuple[str, ...]) -> Self:
        tokens = list(args)

        if '--' not in tokens:
            raise click.UsageError("Missing '--' separator before command")

        separator_idx = tokens.index('--')
        profiles = tokens[:separator_idx]
        command_argv = tokens[separator_idx + 1 :]

        if not profiles:
            raise click.UsageError('Missing profile selection')

        if not command_argv:
            raise click.UsageError('Missing command after --')

        return cls(profiles=profiles, command_argv=command_argv)

    def child_env(self, start_at: Path) -> dict[str, str]:
        conf = config.load(start_at)
        envconf = EnvConfig(conf)
        envconf.validate_selected_names(self.profiles)

        child_env = dict(environ)
        child_env.pop(PROFILES_ENVVAR, None)
        child_env.pop(MANAGED_VARS_ENVVAR, None)
        child_env.update(envconf.resolve_in_order(self.profiles))
        return child_env

    def run(self, start_at: Path) -> int:
        try:
            return subprocess.call(self.command_argv, env=self.child_env(start_at))
        except FileNotFoundError as e:
            raise click.ClickException(f'Command not found: {self.command_argv[0]}') from e
        except PermissionError as e:
            raise click.ClickException(f'Command is not executable: {self.command_argv[0]}') from e
