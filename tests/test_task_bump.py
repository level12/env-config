import datetime as dt
from importlib.machinery import SourceFileLoader
import importlib.util
from pathlib import Path
from unittest import mock

from click.testing import CliRunner
import pytest


def load_bump_mod():
    task_fpath = Path(__file__).resolve().parents[1] / 'tasks' / 'bump'
    loader = SourceFileLoader('task_bump', str(task_fpath))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture()
def bump_mod():
    return load_bump_mod()


class TestVersion:
    def test_load(self, bump_mod, tmp_path: Path):
        version_fpath = tmp_path / 'version.py'
        version_fpath.write_text("VERSION = '1.2.3'\n")

        version = bump_mod.Version.load(version_fpath=version_fpath)

        assert version == bump_mod.Version(1, 2, 3)
        assert version.version_fpath == version_fpath

    def test_save(self, bump_mod, tmp_path: Path):
        version_fpath = tmp_path / 'version.py'
        version_fpath.write_text("VERSION = '1.2.3'\n")

        bump_mod.Version(2, 0, 0, version_fpath=version_fpath).save()

        assert version_fpath.read_text() == "VERSION = '2.0.0'\n"

    def test_date_bump(self, bump_mod):
        version = bump_mod.Version(0, 20250626, 1)

        assert version.bump('date', today=dt.date(2025, 6, 26)) == bump_mod.Version(0, 20250626, 2)
        assert version.bump('date', today=dt.date(2025, 6, 27)) == bump_mod.Version(0, 20250627, 1)


class TestBumpTask:
    def test_major_bump(self, bump_mod, tmp_path: Path):
        previous = bump_mod.Version(0, 20250626, 2, version_fpath=tmp_path / 'version.py')

        with (
            mock.patch.object(bump_mod.Version, 'load', return_value=previous),
            mock.patch.object(bump_mod.Version, 'save', autospec=True) as m_save,
            mock.patch.object(bump_mod, 'sub_run') as m_sub_run,
        ):
            result = CliRunner().invoke(bump_mod.main, ['major'], catch_exceptions=False)

        assert result.output == ''
        saved = m_save.call_args.args[0]
        assert saved == bump_mod.Version(1, 0, 0)
        assert saved.version_fpath == previous.version_fpath
        assert m_sub_run.call_args_list == [
            mock.call('git', 'add', previous.version_fpath),
            mock.call('git', 'commit', '-m', 'Bump version 0.20250626.2 → 1.0.0'),
            mock.call('git', 'tag', '-a', 'v1.0.0', '-m', 'v1.0.0'),
            mock.call('git', 'push', '--follow-tags'),
        ]
