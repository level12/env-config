# System Changes / Agent Permissions

IMPORTANT: the files you edit should only be in this local repo, NEVER anywhere else on
the system.

You, the agent, should NEVER run commands on the system that would make permanent changes
outside the project's repo directory (except for temporary files).

If a command/process you want to run would affect non-temporary files outside the project
directory, the command/process MUST BE READ-ONLY.

If you are ever confused about what you have permission to do, stop and ask.

## Exception: temporary files / directories

Exceptions to the permission policies:

- Ok: changes to files inside known system temporary directories like `/tmp`.
- Ok: create/update runtime artifacts like `.pyc`
- Ok: to make changes with uv that impact this project's venv ONLY
- OK: changes to the databases defined in this app's docker compose

# Conditional Instructions Index

1. At the start of every session, before responding to the first user prompt or doing any
   task-related work, you MUST ALWAYS load the
   [index file](https://raw.githubusercontent.com/rsyring/agent-configs/refs/heads/main/conditional-instructions.yaml)
2. You MUST NOT load any linked documents from that index UNLESS that document's `when`
   condition applies to the current task.
3. If the index file cannot be fetched, stop and report that failure before answering the
   user substantively.
4. WHEN you load a document from the index, notify the user.

# System Commands

- Use ripgrep `/usr/bin/rg` instead of `grep` because it's faster

# File paths prefer dashes

UNLESS it's a `*.py` file, prefer dashes (`-`) in file paths and names instead of
underscores.
