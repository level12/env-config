env-config
==========

Helps manage environment variables in the active shell as defined by an `env-config.yaml`
configuration file.


# Install

Intended to be installed from source directory or GitHub URl with pipx or [uv
tools](https://docs.astral.sh/uv/guides/tools/#installing-tools).

When developing, use [reqs](../reqs-pkg/), and `reqs sync` will install an editable version using
pipx.

## Shell Activation

This assumes that you have your PATH setup to include pipx/uv-tools installed bins:

Bash:

```sh
echo 'eval "$(env-config-shell bash)"' >> ~/.bashrc
```

Fish:

```fish
echo 'env-config-shell fish | source' >> ~/.config/fish/config.fish
```

# Configuration

In the project/app add a `env-config.yaml` configuration file.  Example:

```yaml
# Vars can be referenced in value definitions
var:
  sf_api_prod_prefix: 'op://pylons-bravo7/API - Prod - Alpha Six'
  sf_api_sandbox_prefix: 'op://pylons-bravo7/API - Sandbox - Alpha Six'
  aws_prefix: 'op://pylons-bravo7/Pylons - Prod - Alpha Six AWS'
# Profiles represent logical groupings of environment variables
profile:
  qw-prod:
    ZULU_DB_PASS: 'op://private/Bravo7 SQL Server/password'
  sf-prod:
    SF_API_USERNAME: '{var.sf_api_prod_prefix}/username'
    SF_API_PASSWORD: '{var.sf_api_prod_prefix}/password'
    SF_API_SECURITY_TOKEN: '{var.sf_api_prod_prefix}/Security Token'
  sf-sandbox:
    SF_API_DOMAIN: 'test'
    SF_API_USERNAME: '{var.sf_api_sandbox_prefix}/username'
    SF_API_PASSWORD: '{var.sf_api_sandbox_prefix}/password'
    SF_API_SECURITY_TOKEN: '{var.sf_api_sandbox_prefix}/Security Token'
  aws-prod:
    AWS_ACCESS_KEY_ID: '{var.aws_prefix}/access-key-id'
    AWS_SECRET_ACCESS_KEY: '{var.aws_prefix}/secret-access-key'
  # Demonstrate using an environment variable.  Like a var but from the current environment.
  some-api:
    API_TOKEN: 'op://private/{env.SOME_NON_STANDARD_ITEM_NAME}'

# Groups represent logical groupings of profiles
group:
  # `env-config sync-prod` is equivalent to `env-config qw-prod sf-prod`
  sync-prod:
    - qw-prod
    - sf-prod
  # Groups can only contain profiles, not other groups.
  deploy:
    - aws-prod
    - qw-prod
    - sf-prod

# aws-vault profiles from ~/.aws/config or wherever aws-vault would find them.
aws-vault:
  - some-profile
```

## Usage Example

```fish
 ❯ env-config --list
Profiles:
    pypi
Groups:

 ❯ echo $HATCH_INDEX_USER
# blank

 ❯ env-config pypi
Clearing:
     No configured vars present to clear.
Profiles active: pypi
Setting:
    HATCH_INDEX_USER: __TOKEN__
    HATCH_INDEX_AUTH: op://private/pypi.python.org/api-token

Fish: sourced env-config commands from stdout

 ❯ echo $HATCH_INDEX_USER
__TOKEN__

 ❯ env-config --clear
Clearing:
     HATCH_INDEX_AUTH, HATCH_INDEX_USER

Fish: sourced env-config commands from stdout

 ❯ echo $HATCH_INDEX_USER
# blank
```
