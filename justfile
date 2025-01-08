# Guidelines for new commands
# - Start with a verb
# - Keep it short (max. 3 words in a command)
# - Group commands by context. Include group name in the command name.
# - Mark things private that are util functions with [private] or _var
# - Don't over-engineer, keep it simple.
# - Don't break existing commands
# - Run just --fmt --unstable after adding new commands

set dotenv-load := true

# ---------------------------------------------------------------------------------------------------------------------
# Private vars

_red := '\033[1;31m'
_cyan := '\033[1;36m'
_green := '\033[1;32m'
_yellow := '\033[1;33m'
_nc := '\033[0m'

# ---------------------------------------------------------------------------------------------------------------------
# Aliases

alias rj := run-jupyter

# ---------------------------------------------------------------------------------------------------------------------

@default:
    just --list


[group('utils')]
run-jupyter jupyter_args="":
    uv venv
    uv pip install --reinstall ./syft-event
    uv pip install --reinstall ./syft-files
    uv pip install --reinstall ./syft-requests
    uv pip install --reinstall ./syft-rpc

    uv run --frozen --with "jupyterlab" \
        jupyter lab {{ jupyter_args }}
