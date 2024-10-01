env-config
==========

env-config (EC) helps manage environment variables in the active shell as defined by an
`env-config.yaml` configuration file.  It has built-in support for reading secrets from 1Password.


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
  sf_api_prod_prefix: 'op://pylons-bravo7/API - Prod'
  sf_api_sandbox_prefix: 'op://pylons-bravo7/API - Sandbox'
  aws_prefix: 'op://pylons-bravo7/Pylons - Prod AWS'
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
```

## 1Pass support

Any values that start with 'op://' will be treated as 1Password secret references and resolved using
the 1Password `op` cli tool.  EC assumes that binary is on the PATH if "op" references are being
used.

EC extends the 1Password secret reference format to support specifying the account used to lookup
the secret:

* Normal reference: `op://vault-name/item/field`
* Extended reference: `op://account-ref/vault-name/item/field`
  * EC will call `op --account account-ref -n op://vault-name/item/field`
  * See also `op account list` and `op read --help`
  * account-ref works best as the short form of the account "URL", i.e. "starfleet.1password.com"
    would use "starfleet": `op://starfleet/senior-officers/enterprise/self-destruct-code`


# Usage Example

Using the `env-config.yaml` entry in this repo:

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

# AWS

It's possible the [AWS 1PassCLI plugin](https://developer.1password.com/docs/cli/shell-plugins/aws)
is sufficient for your AWS authentication needs.  However, that plugin is designed in such a way
that only a single AWS account can be used at a time in the shell.

There are situations where you need multiple AWS accounts available at the same time.  E.g. when
using Terraform to create similar intrastructure in more than one account (e.g. dev, beta, prod) and
using different profiles to use a different provider for each account.

It's also possible you'd prefer to use AWS credentials in multiple shells without having to set them
all up individually.  EC has support for these scenarios by acting as an AWS credential process.

The following `~/.aws/config` demonstrates a profile that uses `env-config-aws` to generate and
cache temporary session credentials for the profile:

```ini
[profile starfleet]
region = us-east-2
mfa_serial = arn:aws:iam::12345678910:mfa/1pass-picard

# When an AWS cli tool or library needs to use this profile, it will call `env-config-aws` exactly
# as defined here.  EC will then:
# 1. Read the profile name as an argument and fetch the mfa_serial and
#    envconfig_1pass from this profile.
# 2. Generate temporary session credentials using the envconfig_1pass ref below
# 3. Output those credentials in the format expected by a credential_process to be consumed by AWS
#    tools/libs.
credential_process = env-config-aws starfleet

# The permanent credentials used to generate the temporary session credentials are stored in this
# 1Password item.  The item needs to have the fields:
# - access-key-id
# - secret-access-key
# and, when using MFA, a one-time password which was created for the mfa_serial listed in this profile
envconfig_1pass = op://Employee/aws-starfleet/
```

That profile can then be used without setting any environment variables:

```fish
 ❯ aws sts get-caller-identity --profile starfleet
{
    "UserId": "AIDAJ5RS5OWI4EKSDABC",
    "Account": "12345678910",
    "Arn": "arn:aws:iam::12345678910:user/jpicard"
}
```

env-config can be used to set the profile at the environment level:

```yaml
profile:
  starfleet:
    AWS_PROFILE: starfleet
  starfleet-dev:
    AWS_PROFILE: starfleet-dev
```

```fish
 ❯ env-config starfleet
...
Profiles active: starfleet
Setting:
    AWS_PROFILE: starfleet
...

 ❯ aws sts get-caller-identity
{
    "UserId": "AIDAJ5RS5OWI4EKSDABC",
    "Account": "12345678910",
    "Arn": "arn:aws:iam::12345678910:user/jpicard"
}
```

`env-config-aws` caches the temporary session credentials in a local file to avoid the 1Pass + HTTP
API overhead on every usage of those credentials.  That file has simple (maybe simplistic)
encryption to avoid plain text storage of credentials, which is one small step beyond what the AWS
CLI tools do when generating temporary credentials, which are stored in a plain text file.

If the cached credentials are expired or will expire in the next five minutes, env-config-aws
will automatically refresh them.

To inspect what `env-config-aws` is doing behind the scenes when called by AWS tools/libs, see the
logs at `/tmp/env-config/env-config.log` or your OS's equivalent.

# Development

- Tests & CI: see `.circle/config.yml`
- Release
  - `mise run bump`
  - See github actions for pypi deploy
