#! /bin/sh
set -eu

if [ $# -ne 1 ]; then
    echo "ERROR: Usage: ${0} <cloud_provider>" >&2
    exit 1
fi

PYTHON="$(command -v python3 || command -v python)"
DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
"${PYTHON}" "${DIR}/install-citc.py" "${@}"
