#!/bin/bash
#
# Turbine — Get Started
#
# Clones the Turbine Python SDK and launches Claude Code to walk you
# through setup and bot creation. Claude handles everything from there:
# Python environment, wallet, credentials, algorithm selection, and
# generating your trading bot.
#
# Usage:
#   curl -sSL turbinefi.com/claude | bash
#
# Or with a custom directory:
#   curl -sSL turbinefi.com/claude | bash -s -- ~/my-trading-bot
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

INSTALL_DIR="${1:-turbine-bot}"

echo ""
echo -e "${BLUE}  Turbine — Bitcoin Prediction Markets${NC}"
echo -e "${BLUE}  Build a trading bot with Claude Code${NC}"
echo ""

# --- Check prerequisites ---

if ! command -v git &> /dev/null; then
    echo -e "${RED}Error: git is not installed.${NC}"
    echo ""
    echo "  macOS:   xcode-select --install"
    echo "  Ubuntu:  sudo apt install git"
    echo "  Windows: https://git-scm.com/downloads"
    exit 1
fi

if ! command -v claude &> /dev/null; then
    echo -e "${RED}Error: Claude Code is not installed.${NC}"
    echo ""
    echo "  Install it with:"
    echo "    npm install -g @anthropic-ai/claude-code"
    echo ""
    echo "  Or visit: https://docs.anthropic.com/en/docs/claude-code"
    exit 1
fi

# --- Clone the repo ---

if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Directory '${INSTALL_DIR}' already exists.${NC}"
    if [ -d "$INSTALL_DIR/.git" ]; then
        echo "  Updating..."
        git -C "$INSTALL_DIR" pull --quiet || true
    fi
else
    echo "Cloning turbine-py-client..."
    git clone --quiet https://github.com/ojo-network/turbine-py-client.git "$INSTALL_DIR"
fi

echo -e "${GREEN}Repository ready at ${INSTALL_DIR}/${NC}"
echo ""

# --- Launch Claude Code ---

echo "Launching Claude Code..."
echo "Claude will walk you through setup and help you create your first bot."
echo ""

cd "$INSTALL_DIR"
claude "/setup"
