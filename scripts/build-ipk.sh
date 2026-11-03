#!/bin/sh
# Build the vyoscli .ipk inside an OpenWrt SDK.
#
#   SDK=~/openwrt-sdk-24.10.0-x86-64_gcc-13.3.0_musl.Linux-x86_64 \
#       scripts/build-ipk.sh
#
# The SDK path can also come from the first positional argument, or be
# auto-detected as ~/openwrt-sdk-*. No sudo, no menuconfig: the package is
# enabled in .config directly, so the whole thing is scriptable/CI-friendly.
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PKG_SRC="$REPO_ROOT/package/vyoscli"

SDK="${SDK:-${1:-}}"
if [ -z "$SDK" ]; then
	SDK=$(ls -d "$HOME"/openwrt-sdk-* 2>/dev/null | head -n 1 || true)
fi
if [ -z "$SDK" ] || [ ! -d "$SDK" ]; then
	echo "usage: SDK=/path/to/openwrt-sdk $0 [sdk-path]" >&2
	exit 1
fi
if [ ! -f "$PKG_SRC/Makefile" ]; then
	echo "error: $PKG_SRC/Makefile not found (run from the repo)" >&2
	exit 1
fi

cd "$SDK"
mkdir -p package/utils
# Refresh the in-SDK copy so a stale tree never masks a source change.
rm -rf package/utils/vyoscli
cp -a "$PKG_SRC" package/utils/vyoscli

make defconfig >/dev/null
if grep -q '^CONFIG_PACKAGE_vyoscli=' .config; then
	sed -i 's/^CONFIG_PACKAGE_vyoscli=.*/CONFIG_PACKAGE_vyoscli=y/' .config
else
	echo 'CONFIG_PACKAGE_vyoscli=y' >> .config
fi
make defconfig >/dev/null
grep -q '^CONFIG_PACKAGE_vyoscli=y' .config || {
	echo "error: CONFIG_PACKAGE_vyoscli is not selectable in this SDK" >&2
	echo "hint: check that package/utils/vyoscli/Makefile parses (make menuconfig)" >&2
	exit 1
}

make package/utils/vyoscli/compile V=s

echo
echo "=== ipk ==="
find bin/packages -name 'vyoscli*.ipk' -print
