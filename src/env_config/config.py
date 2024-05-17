from os import environ
from pathlib import Path

import dynamic_yaml
from dynamic_yaml.yaml_wrappers import YamlDict


AWS_VAULT_VARS = (
    'AWS_ACCESS_KEY_ID',
    'AWS_SECRET_ACCESS_KEY',
    'AWS_SESSION_TOKEN',
    'AWS_SECURITY_TOKEN',
    'AWS_VAULT',
    'AWS_SESSION_EXPIRATION',
)


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
        raise Exception(f'{start_at} should be a directory or .yaml file')

    if config_fpath is None:
        relative_path = start_at.relative_to(Path.cwd())
        raise Exception(f'No env-config.yaml in {relative_path} or parents')

    with config_fpath.open() as fo:
        config = dynamic_yaml.load(fo)

    config._collection['env'] = YamlDict(environ)
    config._collection.setdefault('group', {})
    config._collection.setdefault('profile', YamlDict())

    for aws_profile in config.get('aws-vault', ()):
        profile_name = f'aws.{aws_profile}'
        config.profile[profile_name] = YamlDict()
        for varname in AWS_VAULT_VARS:
            config.profile[profile_name][varname] = f'aws-vault://{aws_profile}/{varname}'

    return config
