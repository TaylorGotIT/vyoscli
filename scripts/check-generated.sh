#!/bin/sh
# Fail when a generated artifact is out of date. Usable locally and in CI.
set -eu

cd "$(dirname "$0")/.."

python3 scripts/build-config-tree.py --check
python3 scripts/gen-command-reference.py

if ! git diff --quiet -- docs/COMMANDS.md \
        package/vyoscli/files/usr/lib/vyoscli/config_tree.py; then
	echo "generated artifacts are stale; commit the regenerated files:" >&2
	git diff --stat -- docs/COMMANDS.md \
		package/vyoscli/files/usr/lib/vyoscli/config_tree.py >&2
	exit 1
fi

echo "generated artifacts are up to date"
