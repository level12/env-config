env-config
==========

Helps manage environment variables in the active shell as defined by an `env-config.yaml`
configuration file.


# Install

Intended to be used with pipx

- manually: `pipx install -e .../apps/env-config-pkg`; or
- when developing: `cd .../apps/env-config-pkg;` [`reqs`](../reqs-pkg/) `sync`


## Usage

- Add an `env-config.yaml` file (see next section) to the project.
- Configure shell with `env-config-shell ... | source`
    - Considering adding to your shell's startup scripts
- `env-config profile-or-group names here`: to setup the current shell's env according to the given
  profiles.
- `env-config`: to see what profiles and vars from env-config are active
- `env-config --help` for more usage options


# Configuration

In the project/app add a `env-config.yaml` configuration file.  Example:

```yaml
# Vars can be referenced in value definitions
var:
  sf_api_prod_prefix: 'op://pylons-alphasix/API - Prod - Alpha Six'
  sf_api_sandbox_prefix: 'op://pylons-alphasix/API - Sandbox - Alpha Six'
  aws_prefix: 'op://pylons-alphasix/Pylons - Prod - Alpha Six AWS'
# Profiles represent logical groupings of environment variables
profile:
  qw-prod:
    ZULU_DB_PASS: 'op://private/AlphaSix SQL Server/password'
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
