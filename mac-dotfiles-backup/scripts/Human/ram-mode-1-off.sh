#!/bin/bash
# RAM Mode 1 — OFF (reverse of ram-mode-1.sh)
# Re-enables Spotlight indexing, reloads the jcode hotkey listener,
# and relaunches cloud sync apps that Mode 1 killed.

echo "=== RAM Mode 1: OFF ==="

echo ""
echo ">> Spotlight (resume indexing)"
sudo mdutil -a -i on 2>/dev/null && echo "  spotlight indexing resumed"

echo ""
echo ">> jcode hotkey listener"
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jcode.hotkey.plist 2>/dev/null && echo "  reloaded: com.jcode.hotkey" || echo "  already loaded: com.jcode.hotkey"

echo ""
echo ">> Cloud sync"
open -a "OneDrive" 2>/dev/null && echo "  relaunched: OneDrive"
open -a "Google Drive" 2>/dev/null && echo "  relaunched: Google Drive"

echo ""
echo ">> Desktop tools"
open -a "boringNotch" 2>/dev/null && echo "  relaunched: boringNotch"
open -a "Gemini" 2>/dev/null && echo "  relaunched: Gemini"

echo ""
echo "=== Done. RAM Mode 1 reverted ==="
