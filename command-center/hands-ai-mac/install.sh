#!/bin/zsh
# Build, sign and install Hammond (Hands AI) — one command instead of a
# hand-typed sequence each time.   ./install.sh
# Hammond runs under launchd (com.natehoward.hammond, relaunch-on-crash), so
# it's booted out before the copy (a plain kill would make launchd relaunch
# the OLD binary) and booted back in after.
set -euo pipefail
cd "${0:A:h}"
S="${TMPDIR:-/tmp}/hammond-build"
IDENTITY="Apple Development: np.howard9@gmail.com (GR4B3F8BNM)"
AGENT=~/Library/LaunchAgents/com.natehoward.hammond.plist

echo "→ building"
xcodebuild -project HandsAI.xcodeproj -scheme HandsAI -configuration Release \
  -derivedDataPath "$S" build 2>&1 | grep -E "error:|BUILD (SUCCEEDED|FAILED)"
APP="$S/Build/Products/Release/Hands AI.app"
[[ -d "$APP" ]] || { echo "build produced no app"; exit 1; }

echo "→ signing (same identity + entitlements as the installed app)"
codesign -d --entitlements :- "/Applications/Hands AI.app" > "$S/hands.ent" 2>/dev/null || true
codesign --force --deep --options runtime --entitlements "$S/hands.ent" --sign "$IDENTITY" "$APP"

echo "→ stopping Hammond"
launchctl bootout "gui/$(id -u)/com.natehoward.hammond" 2>/dev/null || true
pkill -TERM -f "Hands AI.app/Contents/MacOS" 2>/dev/null || true
sleep 3

echo "→ installing"
for d in /Applications ~/Applications; do rm -rf "$d/Hands AI.app"; ditto "$APP" "$d/Hands AI.app"; done

echo "→ starting"
if [[ -f "$AGENT" ]]; then launchctl bootstrap "gui/$(id -u)" "$AGENT"; else open "/Applications/Hands AI.app"; fi
for i in {1..15}; do lsof -nP -iTCP:8787 -sTCP:LISTEN >/dev/null 2>&1 && { echo "✓ Hammond is up (port 8787)"; exit 0; }; sleep 1; done
echo "✗ Hammond didn't start listening on 8787"; exit 1
