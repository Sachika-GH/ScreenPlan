#!/bin/bash
# ============================================================
# ScreenPlan macOS Agent - launchd Installation Script
#
# Usage:
#   bash install_launchd.sh       # Install and start
#   bash install_launchd.sh uninstall  # Uninstall
# ============================================================
set -e

PLIST_SRC="$(dirname "$0")/com.screenplan.agent.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.screenplan.agent.plist"
AGENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$AGENT_DIR/data"

if [ "$1" = "uninstall" ]; then
    echo "=== Uninstalling ScreenPlan Agent launchd ==="
    launchctl unload "$PLIST_DST" 2>/dev/null || true
    rm -f "$PLIST_DST"
    echo "✅ Uninstalled"
    exit 0
fi

echo "=== Installing ScreenPlan Agent launchd ==="
echo "  Agent dir: $AGENT_DIR"

# Create data dir
mkdir -p "$DATA_DIR"

# Update plist with correct paths
TMP_PLIST="/tmp/com.screenplan.agent.plist"
cp "$PLIST_SRC" "$TMP_PLIST"

# Replace placeholder paths with actual paths
/usr/libexec/PlistBuddy -c "Set ProgramArguments:1 $AGENT_DIR/main.py" "$TMP_PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set WorkingDirectory $AGENT_DIR" "$TMP_PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set StandardOutPath $DATA_DIR/launchd.log" "$TMP_PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set StandardErrorPath $DATA_DIR/launchd.err" "$TMP_PLIST" 2>/dev/null || true

# Install plist
mkdir -p "$HOME/Library/LaunchAgents"
cp "$TMP_PLIST" "$PLIST_DST"
rm "$TMP_PLIST"

# Unload if already loaded
launchctl unload "$PLIST_DST" 2>/dev/null || true

# Load (start + enable on boot)
launchctl load "$PLIST_DST"

echo ""
echo "=============================================="
echo "  ✅ ScreenPlan Agent 已安装并启动"
echo "=============================================="
echo ""
echo "  状态检查:"
echo "    launchctl list | grep screenplan"
echo ""
echo "  查看日志:"
echo "    tail -f $DATA_DIR/launchd.log"
echo "    tail -f $DATA_DIR/launchd.err"
echo ""
echo "  卸载:"
echo "    bash $0 uninstall"
