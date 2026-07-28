#!/bin/zsh
set -e
cd "$(dirname "$0")"
swift build -c release
APP=~/Applications/MyApps.app
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp .build/release/MyApps "$APP/Contents/MacOS/MyApps"
cat > "$APP/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key><string>MyApps</string>
    <key>CFBundleIdentifier</key><string>com.nate.myapps</string>
    <key>CFBundleName</key><string>My Apps</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleShortVersionString</key><string>1.0</string>
    <key>LSMinimumSystemVersion</key><string>14.0</string>
    <key>NSHighResolutionCapable</key><true/>
    <key>CFBundleIconFile</key><string>AppIcon</string>
</dict>
</plist>
PLIST
mkdir -p "$APP/Contents/Resources"
actool --compile "$APP/Contents/Resources" --platform macosx --minimum-deployment-target 14.0 --app-icon AppIcon Assets.xcassets
codesign --force --deep --sign - "$APP"
echo "Built $APP"
