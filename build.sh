#!/usr/bin/env bash
# Build Structura using the canonical universal-build.sh
# This script delegates to .razorcore/universal-build.sh to ensure consistent
# uv toolchain, PyInstaller settings, ad-hoc signing, and the shared DMG layout.
#
# Note: the DMG volume icon (previously set here via --volicon) is now derived
# automatically from the app bundle's own .icns, and the bundle identifier comes
# from Structura.spec (bundle_identifier='com.github.razorbackroar.structura'),
# so signing behavior is unchanged. DMG layout is the single shared config in
# .razorcore/dmg-settings.py — do not reintroduce a local create-dmg call.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAZORCORE_DIR="$SCRIPT_DIR/../.razorcore"

exec bash "$RAZORCORE_DIR/universal-build.sh" "Structura" "$@"
