#!/bin/sh
# Fail when a generated artifact is out of date. Usable locally and in CI.
set -eu

cd "$(dirname "$0")/.."

python3 scripts/gen-command-reference.py

if ! git diff --quiet -- docs/COMMANDS.md; then
	echo "docs/COMMANDS.md is stale; commit the regenerated file:" >&2
	git diff -- docs/COMMANDS.md | head -40 >&2
	exit 1
fi

echo "generated docs are up to date"
