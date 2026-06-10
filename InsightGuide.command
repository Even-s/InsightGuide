#!/bin/bash
# Double-click launcher for macOS Finder.

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

./insightguide.sh launch

echo ""
echo "InsightGuide launcher finished. You can close this window."
echo "Press Enter to close."
read -r _
