from os import environ
from pathlib import Path

import pexpect
import pytest


basics_fpath = Path(__file__).parent / 'configs' / 'basics.yaml'


class TestBash:
    @pytest.fixture
    def bash(self, tmp_path):
        # TERM: no color codes
        # PS1: blank prompt
        env = environ | {'TERM': 'DUMB', 'PS1': ''}
        bash = pexpect.spawn(
            'bash',
            # Options are to avoid bash contamination from dev's init files and keep tests
            # consistent across hosts.
            ['--noprofile', '--norc'],
            echo=False,
            encoding='utf-8',
            cwd=tmp_path,
            timeout=2,
            env=env,
        )
        # NOTE: the next line should match the instructions given in the readme
        bash.sendline('eval "$(env-config-shell bash)"')
        return bash

    def test_basics(self, bash: pexpect.spawn, tmp_path):
        bash.sendline(f"env-config --config '{basics_fpath}' --list")
        bash.expect('starfleet')

        bash.sendline(f"env-config --config '{basics_fpath}' starfleet")
        bash.expect('Bash: sourced env-config commands from stdout')
        bash.sendline('echo $PICARD')
        bash.expect('captain')
        bash.sendline('echo $_ENV_CONFIG_PROFILES')
        bash.expect('starfleet')

        bash.sendline(f"env-config --config '{basics_fpath}' --clear")
        bash.expect('Bash: sourced env-config commands from stdout\r\n')

        # Output should be blank
        bash.sendline('echo $PICARD')
        bash.expect('\r\n')
        assert bash.before == ''

        # Output should be blank
        bash.sendline('echo $_ENV_CONFIG_PROFILES')
        bash.expect('\r\n')
        assert bash.before == ''


class TestFish:
    @pytest.fixture
    def fish(self, tmp_path):
        env = {'TERM': 'dumb', 'PATH': environ['PATH']}
        fish = pexpect.spawn(
            'fish',
            # Options are to avoid contamination from dev's init files and keep tests
            # consistent across hosts.
            ['--no-config'],
            echo=False,
            encoding='utf-8',
            cwd=tmp_path,
            timeout=2,
            env=env,
        )
        fish.sendline("function fish_prompt; echo -n '>>> '; end;")
        # NOTE: the next line should match the instructions given in the readme
        fish.sendline('env-config-shell fish | source')
        return fish

    def test_basics(self, fish: pexpect.spawn, tmp_path):
        fish.sendline(f"env-config --config '{basics_fpath}' --list")
        fish.expect('starfleet')

        fish.sendline(f"env-config --config '{basics_fpath}' starfleet")
        fish.expect('Fish: sourced env-config commands from stdout')

        fish.sendline('echo $PICARD')
        fish.expect('captain\r\n')

        fish.sendline('echo $_ENV_CONFIG_PROFILES')
        fish.expect('starfleet\r\n')

        fish.sendline(f"env-config --config '{basics_fpath}' --clear")
        fish.expect('Fish: sourced env-config commands from stdout\r\n')

        # Output should be blank
        fish.sendline('set --names')
        # Not sure why the command is being echoed.
        # See: https://github.com/fish-shell/fish-shell/discussions/10747
        fish.expect('>>> set --names\r\n')
        fish.expect('>>>')
        assert 'PICARD' not in fish.before
        assert '_ENV_CONFIG_PROFILES' not in fish.before
