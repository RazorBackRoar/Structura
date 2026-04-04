#!/usr/bin/env bash
set -euo pipefail

# Structura build pipeline: PyInstaller → codesign → DMG
# Usage: ./build.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="Structura"
BUNDLE_ID="com.github.razorbackroar.structura"
ICON_FILE="assets/Structura.icns"
SPEC_FILE="Structura.spec"
DIST_DIR="dist"

echo "=== Syncing dependencies ==="
uv sync

echo "=== Building ${APP_NAME}.app (arm64) ==="
PYINSTALLER_TARGET_ARCH=arm64 uv run pyinstaller --clean --noconfirm "$SPEC_FILE"

echo ""
echo "=== Signing ${APP_NAME}.app (ad-hoc) ==="
codesign --deep --force --sign - \
  --identifier "$BUNDLE_ID" \
  "${DIST_DIR}/${APP_NAME}.app"

echo ""
echo "=== Verifying signature (strict) ==="
codesign --verify --deep --strict --verbose=2 "${DIST_DIR}/${APP_NAME}.app"

echo ""
echo "=== Signature details ==="
codesign -dv "${DIST_DIR}/${APP_NAME}.app"

echo ""
echo "=== Creating ${APP_NAME}.dmg ==="
rm -f "${DIST_DIR}/${APP_NAME}.dmg"

create-dmg \
  --volname "$APP_NAME" \
  --volicon "$ICON_FILE" \
  --window-pos 200 120 \
  --window-size 600 350 \
  --icon-size 100 \
  --icon "${APP_NAME}.app" 175 150 \
  --app-drop-link 425 150 \
  --no-internet-enable \
  "${DIST_DIR}/${APP_NAME}.dmg" \
  "${DIST_DIR}/${APP_NAME}.app"

echo ""
echo "=== Done ==="
echo "App:  ${DIST_DIR}/${APP_NAME}.app"
echo "DMG:  ${DIST_DIR}/${APP_NAME}.dmg"
du -sh "${DIST_DIR}/${APP_NAME}.app" "${DIST_DIR}/${APP_NAME}.dmg"
