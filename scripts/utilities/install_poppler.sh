#!/bin/bash

# Poppler Installation Script for InsightGuide
# This script attempts to install Poppler using available package managers

set -e

echo "================================================"
echo "  InsightGuide - Poppler Installation Script"
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if pdfinfo already exists
if command -v pdfinfo &> /dev/null; then
    echo -e "${GREEN}✓ Poppler is already installed!${NC}"
    pdfinfo -v
    exit 0
fi

echo -e "${YELLOW}⚠ Poppler is not installed. Attempting to install...${NC}"
echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Try Homebrew
if command_exists brew; then
    echo -e "${GREEN}Found Homebrew. Installing poppler...${NC}"
    brew install poppler

    if command -v pdfinfo &> /dev/null; then
        echo -e "${GREEN}✓ Poppler installed successfully via Homebrew!${NC}"
        pdfinfo -v
        exit 0
    fi
fi

# Try finding Homebrew in common locations
for brew_path in /usr/local/bin/brew /opt/homebrew/bin/brew; do
    if [ -f "$brew_path" ]; then
        echo -e "${GREEN}Found Homebrew at $brew_path${NC}"
        $brew_path install poppler

        if command -v pdfinfo &> /dev/null; then
            echo -e "${GREEN}✓ Poppler installed successfully via Homebrew!${NC}"
            pdfinfo -v
            exit 0
        fi
    fi
done

# Try MacPorts
if command_exists port; then
    echo -e "${GREEN}Found MacPorts. Installing poppler...${NC}"
    sudo port install poppler

    if command -v pdfinfo &> /dev/null; then
        echo -e "${GREEN}✓ Poppler installed successfully via MacPorts!${NC}"
        pdfinfo -v
        exit 0
    fi
fi

# Try conda
if command_exists conda; then
    echo -e "${GREEN}Found Conda. Installing poppler...${NC}"
    conda install -c conda-forge poppler -y

    if command -v pdfinfo &> /dev/null; then
        echo -e "${GREEN}✓ Poppler installed successfully via Conda!${NC}"
        pdfinfo -v
        exit 0
    fi
fi

# If nothing worked, provide manual instructions
echo ""
echo -e "${RED}✗ Could not automatically install Poppler.${NC}"
echo ""
echo "Please install Poppler manually using one of these methods:"
echo ""
echo "1. Install Homebrew first, then Poppler:"
echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
echo "   brew install poppler"
echo ""
echo "2. Or download pre-compiled binaries from:"
echo "   https://poppler.freedesktop.org/"
echo ""
echo "3. Or see detailed instructions in:"
echo "   POPPLER_INSTALLATION_GUIDE.md"
echo ""
exit 1
