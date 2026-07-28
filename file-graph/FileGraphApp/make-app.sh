#!/bin/zsh
# Build FileGraph.app from the SPM release binary.
set -e
cd "$(dirname "$0")"
swift build -c release
APP=~/Applications/FileGraph.app
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp .build/release/FileGraph "$APP/Contents/MacOS/FileGraph"
cat > "$APP/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key><string>FileGraph</string>
    <key>CFBundleIdentifier</key><string>com.nate.filegraph</string>
    <key>CFBundleName</key><string>File Graph</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleShortVersionString</key><string>1.0</string>
    <key>LSMinimumSystemVersion</key><string>14.0</string>
    <key>NSHighResolutionCapable</key><true/>
    <key>CFBundleIconFile</key><string>AppIcon</string>
</dict>
</plist>
EOF
mkdir -p "$APP/Contents/Resources"
actool --compile "$APP/Contents/Resources" --platform macosx --minimum-deployment-target 14.0 --app-icon AppIcon Assets.xcassets
codesign --force --deep --sign - "$APP"
echo "Built $APP"
