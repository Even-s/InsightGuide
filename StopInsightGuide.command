#!/bin/bash
# Double-click shutdown command for macOS Finder.

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

echo "Stopping InsightGuide..."
echo ""

if ./insightguide.sh stop; then
    echo ""
    echo "InsightGuide has been stopped."
else
    status=$?
    echo ""
    echo "InsightGuide could not be stopped completely (exit code: $status)."
    echo "Run ./insightguide.sh status for details."
fi

echo ""
echo "Press Enter to close this window."
read -r _
