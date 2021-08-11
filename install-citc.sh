#! /bin/sh
set -eu

PYTHON="$(command -v python3 || command -v python)"
DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
"${PYTHON}" "${DIR}/install-citc.py" "${@}"
