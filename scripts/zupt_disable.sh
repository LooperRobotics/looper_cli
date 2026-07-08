#!/usr/bin/env bash
#
# Set use_zupt = false in the device VIO config and restart insight_full.
#
# The SSH password is read from the LOOPER_SSH_PASSWORD environment variable so
# it never appears in the command line (and is not visible in `ps`). Either edit
# the placeholder below, or export LOOPER_SSH_PASSWORD before running this script.
#
# Any extra arguments are passed through to the CLI, e.g.:
#   ./scripts/zupt_disable.sh --ssh-user root --ssh-host 169.254.10.1
#
set -euo pipefail

export LOOPER_SSH_PASSWORD="${LOOPER_SSH_PASSWORD:-CHANGE_ME}"

cd "$(dirname "$0")/.."
exec python3 looper_cli.py zupt disable -y "$@"
