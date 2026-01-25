#!/bin/bash
#
# Turbine Market Maker Bot Generator
#
# This script sets up a market maker bot for Turbine's Bitcoin prediction markets.
# It will clone the SDK, install dependencies, and use Claude Code to generate
# a customized trading bot based on your preferences.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/ojo-network/turbine-py-client/main/scripts/create-bot.sh | bash
#
# Or with a specific directory:
#   curl -fsSL https://raw.githubusercontent.com/ojo-network/turbine-py-client/main/scripts/create-bot.sh | bash -s -- ~/my-trading-bot
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default installation directory
INSTALL_DIR="${1:-turbine-bot}"

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║         TURBINE MARKET MAKER BOT GENERATOR                    ║"
echo "║                                                               ║"
echo "║  Create a custom trading bot for Bitcoin prediction markets   ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check for required tools
check_requirements() {
    local missing=()

    if ! command -v git &> /dev/null; then
        missing+=("git")
    fi

    if ! command -v python3 &> /dev/null; then
        missing+=("python3")
    fi

    if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
        missing+=("pip")
    fi

    if ! command -v claude &> /dev/null; then
        echo -e "${YELLOW}Warning: Claude Code CLI not found.${NC}"
        echo ""
        echo "Claude Code is required to generate your custom bot."
        echo "Install it with: npm install -g @anthropic-ai/claude-code"
        echo ""
        echo "Or visit: https://docs.anthropic.com/en/docs/claude-code"
        echo ""
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    if [ ${#missing[@]} -ne 0 ]; then
        echo -e "${RED}Error: Missing required tools: ${missing[*]}${NC}"
        echo "Please install them and try again."
        exit 1
    fi
}

# Clone or update the repository
setup_repo() {
    if [ -d "$INSTALL_DIR" ]; then
        echo -e "${YELLOW}Directory '$INSTALL_DIR' already exists.${NC}"
        read -p "Use existing directory? (Y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            echo "Aborting."
            exit 1
        fi
        cd "$INSTALL_DIR"

        # Check if it's a git repo and update
        if [ -d ".git" ]; then
            echo "Updating repository..."
            git pull --quiet || true
        fi
    else
        echo -e "${GREEN}Cloning Turbine Python SDK...${NC}"
        git clone --quiet https://github.com/ojo-network/turbine-py-client.git "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
}

# Install Python dependencies
install_deps() {
    echo -e "${GREEN}Installing Python dependencies...${NC}"

    # Prefer pip3 but fall back to pip
    PIP_CMD="pip3"
    if ! command -v pip3 &> /dev/null; then
        PIP_CMD="pip"
    fi

    # Install in user space to avoid permission issues
    $PIP_CMD install --quiet --user -e . python-dotenv 2>/dev/null || \
    $PIP_CMD install --quiet -e . python-dotenv
}

# Setup environment file
setup_env() {
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            echo -e "${GREEN}Created .env file from template.${NC}"
        else
            cat > .env << 'EOF'
# Turbine Trading Bot Configuration

# Required: Your Ethereum wallet private key
TURBINE_PRIVATE_KEY=0x...your_private_key_here...

# Auto-generated on first run
TURBINE_API_KEY_ID=
TURBINE_API_PRIVATE_KEY=
EOF
            echo -e "${GREEN}Created .env file.${NC}"
        fi

        echo ""
        echo -e "${YELLOW}IMPORTANT: You need to add your Ethereum private key to .env${NC}"
        echo ""
        echo "  1. Open .env in your editor"
        echo "  2. Replace the TURBINE_PRIVATE_KEY value with your actual key"
        echo "  3. Use a dedicated trading wallet with limited funds!"
        echo ""
    else
        echo -e "${GREEN}.env file already exists.${NC}"
    fi
}

# Run Claude Code to generate the bot
run_claude() {
    if command -v claude &> /dev/null; then
        echo ""
        echo -e "${GREEN}Launching Claude Code to generate your bot...${NC}"
        echo ""
        echo "Claude will ask you to choose a trading algorithm."
        echo "Answer the prompts to customize your bot!"
        echo ""
        echo "─────────────────────────────────────────────────────────"
        echo ""

        # Run claude with the market-maker skill
        claude "/market-maker"
    else
        echo ""
        echo -e "${YELLOW}Claude Code not installed. Manual setup required.${NC}"
        echo ""
        echo "To generate your bot manually:"
        echo "  1. Install Claude Code: npm install -g @anthropic-ai/claude-code"
        echo "  2. Run: cd $INSTALL_DIR && claude \"/market-maker\""
        echo ""
        echo "Or use the pre-built example bot:"
        echo "  python examples/simple_spread_market_maker.py"
        echo ""
    fi
}

# Main execution
main() {
    echo "Checking requirements..."
    check_requirements

    echo ""
    setup_repo

    echo ""
    install_deps

    echo ""
    setup_env

    run_claude
}

main
