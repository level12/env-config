## Feature Spec: `env-config-run`

Refs: https://github.com/level12/env-config/issues/19

### Status

- Ready for implementation

### Summary

Add an `env-config-run` command that resolves one or more env-config profiles,
injects the resulting environment variables into a child process, and runs that
process without changing the parent shell environment.

Example:

`env-config-run db-prod api-dev -- pg_dump ...`

This is intended to be the `env-config` equivalent of `op run`.

### Goals

- Run a child command with env vars from selected profiles.
- Keep env changes scoped to the child process only.
- Preserve normal child process interactivity and streaming stdout/stderr.
- Reuse existing config/profile resolution and secret loading behavior where possible.
- Use CLI syntax that feels familiar to users of `op run` and similar tools.

### Non-goals

- No persistent change to the calling shell environment.
- No background credential server or long-lived refresh daemon.
- No attempt to mask secrets emitted by arbitrary child processes in v1.

### Proposed CLI

Primary form:

- `env-config-run <profile>... -- <command> [args...]`

Installed as a separate top-level command, analogous to `env-config-aws`.

Example:

- `env-config-run db-prod api-dev -- pg_dump ...`

### Expected Behavior

1. Load config using the same config discovery rules as normal `env-config`.
2. Validate the selected profile/group names.
3. Resolve env vars for the selected names, including 1Password-backed values.
4. Start the requested child process with inherited environment plus injected vars.
5. Stream child stdin/stdout/stderr directly.
6. Exit with the child process's exit code.

### Why this shape

Research findings from similar tools:

- `op run -- <command>` uses a separator and runs a subprocess with injected env.
- `dotenvx run -- <command>` uses the same separator and documents shell expansion
  pitfalls.
- `aws-vault exec profile -- <command>` runs a subprocess with direct stdio and can
  also launch a subshell when no command is given.
- `chamber exec service1 service2 -- <command>` overlays env from multiple sources,
  with later sources winning on collisions.

This makes `env-config-run` with a `--` command separator a familiar and reasonable
design.

### Required implementation constraints

#### 1. Direct process execution, not shell-source output

Current `env-config` usage is built around printing shell code to stdout and having a
shell wrapper source/eval it. That approach is not correct for `env-config-run` because it
would buffer output and break interactive programs.

`env-config-run` must take a separate execution path that directly launches the child
process.

#### 2. Child environment model

The child process should receive:

- the current process environment
- plus resolved vars from selected env-config profiles

The child process should not modify the parent shell.

Run mode should reuse `config.load(...)`, selected-name validation, and env value
resolution logic. It should not reuse the shell-emitting `BashEnvConfig.set()` /
`FishEnvConfig.set()` paths.

#### 3. Command separator

Use `--` before the child command to clearly separate env-config arguments from child
command arguments.

### Final behavior decisions

#### Variable collision behavior

When the same env var is defined multiple times, `env-config-run` merges selections in
CLI order and later values win.

Groups expand in place using the profile order declared in the group definition.

If a selected name exists as both a profile and a group, that token resolves as the
profile, matching current `env-config` behavior.

Worked example:

- group `stack` includes `base`, then `api`
- `base` sets `DB_HOST=base`
- `api` sets `DB_HOST=api`
- `override` sets `DB_HOST=override`
- `env-config-run stack override -- cmd` results in `DB_HOST=override`

This CLI-ordered merge path is new and is only for `env-config-run`. Existing
`env-config` selection/emit behavior should remain unchanged.

#### Existing environment behavior

`env-config-run` inherits the current environment, then overlays resolved env-config
vars. There is no pristine mode.

#### Env-config metadata variables

The parent shell today uses internal metadata vars such as `_ENV_CONFIG_PROFILES` and
`_ENV_CONFIG_VARS`.

`env-config-run` must remove `_ENV_CONFIG_PROFILES` and `_ENV_CONFIG_VARS` from the
child environment, even if they are present in the parent shell.

#### Logging and stderr output

On successful execution, `env-config-run` prints nothing itself. Only the child
process's stdout/stderr should be visible.

Error messages from `env-config-run` itself are still allowed for invalid usage,
config/selection errors, and executable launch failures.

#### `--debug`

`env-config-run` does not support `--debug`. Treat it as an invalid option.

#### Interactive shell fallback

`env-config-run` requires a command after `--`. It does not open a subshell when no
command is provided. Users who want a shell can pass their shell binary explicitly.

#### Process model

`env-config-run` should invoke the target command via `subprocess.call(...)` with an
explicit child environment. This keeps the implementation in a normal Click command
path while still streaming the child process's stdio and returning its exit code.

If the target executable cannot be found, `env-config-run` should fail with a non-zero
exit code and a clear error.

#### Argument parsing

The command should be implemented as a Click command that accepts one raw variadic
argument tuple and then splits that tuple at `--`.

Only documented options before the separator are supported.

#### Shell expansion caveat

Like `op run` and `dotenvx run`, the parent shell expands `$VARS` before invoking the
tool. Users expecting post-injection expansion will need to use a subshell, e.g.
`sh -c 'echo "$DB_URL"'`.

This should be documented clearly.

### Error handling

- Unknown profile/group: fail before launching child process.
- Missing command after `env-config-run`: fail with usage help.
- Missing `--` separator: fail with usage help.
- Secret resolution failure: fail before launching child process.
- Child executable not found: fail clearly and return a non-zero exit status.

### Command surface

Expected behavior:

- `env-config-run` should support `--config`
- `env-config-run` may support `--help`
- `env-config-run` should not require `--shell`
- `env-config-run` should not inherit shell-source/list/clear/update behaviors from
  `env-config`
- `env-config-run` should not support `--debug`

### Validation expectations

When implemented, validate at least:

- direct command execution with streamed stdout/stderr
- interactive command compatibility
- child exit code passthrough
- Ctrl-C / signal behavior that is acceptable for the subprocess model
- multi-profile merge order
- group selection behavior
- profile-over-group token selection when names collide
- command parsing after `--`
- metadata vars stripped from child env
- no parent-shell env mutation
