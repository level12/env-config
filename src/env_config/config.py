from os import environ
from pathlib import Path

import dynamic_yaml
from dynamic_yaml.yaml_wrappers import YamlDict

from . import core


def find_upwards(d: Path, filename: str):
    root = Path(d.root)

    while d != root:
        attempt = d / filename
        if attempt.exists():
            return attempt
        d = d.parent

    return None


def load(start_at: Path):
    if start_at.is_dir():
        config_fpath = find_upwards(start_at, 'env-config.yaml')
    elif start_at.suffix == '.yaml':
        config_fpath = start_at
    else:
        raise core.UserError(f'{start_at} should be a directory or .yaml file')

    if config_fpath is None:
        raise core.UserError(f'No env-config.yaml in {start_at} or parents')

    with config_fpath.open() as fo:
        config = dynamic_yaml.load(fo)

    config._collection['env'] = YamlDict(environ)
    config._collection.setdefault('group', {})
    config._collection.setdefault('profile', YamlDict())

    return config
