#!/bin/bash
# RAM Mode 1 — Kill CPU/memory hogs and non-essential background services
# Safe to run anytime. Does not touch system daemons.

echo "=== RAM Mode 1 ==="

kill_if_running() {
  local name="$1"
  if pgrep -x "$name" &>/dev/null; then
    killall "$name" 2>/dev/null && echo "  killed: $name" || echo "  failed: $name"
  fi
}

echo ""
echo ">> Cloud sync (biggest offenders)"
kill_if_running "OneDrive"
kill_if_running "OneDriveStandaloneUpdater"
kill_if_running "Google Drive"

echo ""
echo ">> Siri + intelligence stack"
kill_if_running "assistantd"
kill_if_running "siriknowledged"
kill_if_running "siriactionsd"
kill_if_running "siriinferenced"
kill_if_running "sirittsd"
kill_if_running "Siri"
kill_if_running "SiriNCService"
kill_if_running "suggestd"
kill_if_running "duetexpertd"
kill_if_running "routined"
kill_if_running "knowledge-agent"
kill_if_running "proactived"

echo ""
echo ">> Apple telemetry + analytics"
kill_if_running "analyticsd"
kill_if_running "analyticsagent"
kill_if_running "BiomeAgent"
kill_if_running "biomed"
kill_if_running "promotedcontentd"
kill_if_running "CloudTelemetryService"
kill_if_running "UsageTrackingAgent"
kill_if_running "sysmond"

echo ""
echo ">> Media + photo analysis"
kill_if_running "mediaanalysisd"
kill_if_running "photoanalysisd"
kill_if_running "mediaremoteagent"
kill_if_running "postersyncd"
kill_if_running "replayd"

echo ""
echo ">> Contacts + address book sync"
kill_if_running "AddressBookSourceSync"
kill_if_running "dataaccessd"
kill_if_running "peopled"

echo ""
echo ">> Optional desktop tools"
kill_if_running "Übersicht"
kill_if_running "ChatGPTHelper"
kill_if_running "WeatherMenu"
kill_if_running "boringNotch"
kill_if_running "BoringNotchXPCHelper"
kill_if_running "GeminiAppLauncher"

echo ""
echo ">> jcode hotkey listener (LaunchAgent — unload so it stays down)"
launchctl bootout gui/$(id -u)/com.jcode.hotkey 2>/dev/null && echo "  unloaded: com.jcode.hotkey" || echo "  already unloaded: com.jcode.hotkey"

echo ""
echo ">> Stray dev processes (node/python helpers left running detached)"
pkill -f "node server.js" 2>/dev/null && echo "  killed: node server.js"
pkill -f "proxy.py" 2>/dev/null && echo "  killed: proxy.py"
pkill -f "filegraph serve" 2>/dev/null && echo "  killed: filegraph serve"
pkill -f "clap_detector.py" 2>/dev/null && echo "  killed: clap_detector.py"

echo ""
echo ">> ThinPrint (3rd-party print service)"
kill_if_running "TPAutoConnect"
sudo killall "com.ThinPrint.TPAutoConnSvc" 2>/dev/null && echo "  killed: ThinPrint service"

echo ""
echo ">> Spotlight (pause indexing)"
sudo mdutil -a -i off 2>/dev/null && echo "  spotlight indexing paused"

echo ""
echo ">> Purge file system cache"
sudo purge 2>/dev/null && echo "  memory purged"

echo ""
echo "=== Done. RAM Mode 1 complete ==="
