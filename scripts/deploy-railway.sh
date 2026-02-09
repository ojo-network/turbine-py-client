#!/bin/bash
#
# Turbine Bot - Railway Deployment
#
# Deploy your Turbine trading bot to Railway for 24/7 cloud operation.
# Railway's free tier includes a $5 credit for 30 days — plenty for a small bot.
#
# Usage:
#   bash scripts/deploy-railway.sh
#
# Or after creating a bot:
#   claude "/railway-deploy"
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║         TURBINE BOT - RAILWAY DEPLOYMENT                    ║"
echo "║                                                             ║"
echo "║  Deploy your trading bot to Railway for 24/7 operation      ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Install Railway CLI
install_railway() {
    # Try Homebrew first (macOS)
    if command -v brew &> /dev/null; then
        echo "  Installing via Homebrew..."
        brew install railway
    # Try npm
    elif command -v npm &> /dev/null; then
        echo "  Installing via npm..."
        npm i -g @railway/cli
    # Fallback to shell installer
    else
        echo "  Installing via shell script..."
        bash <(curl -fsSL cli.new)
    fi

    # Verify installation
    if ! command -v railway &> /dev/null; then
        echo -e "${RED}Failed to install Railway CLI.${NC}"
        echo ""
        echo "Install manually with one of:"
        echo "  brew install railway          # macOS (Homebrew)"
        echo "  npm i -g @railway/cli         # Any platform (Node.js)"
        echo "  bash <(curl -fsSL cli.new)    # macOS/Linux"
        exit 1
    fi

    echo -e "${GREEN}Railway CLI installed.${NC}"
}

# Check for required tools
check_requirements() {
    local missing=()

    if ! command -v railway &> /dev/null; then
        echo -e "${YELLOW}Railway CLI not found. Installing...${NC}"
        install_railway
    fi

    if ! command -v python3 &> /dev/null; then
        missing+=("python3")
    fi

    if [ ! -f ".env" ]; then
        echo -e "${RED}Error: No .env file found.${NC}"
        echo ""
        echo "Set up your environment first:"
        echo "  claude \"/setup\""
        echo ""
        echo "Or create a .env file manually with your credentials."
        exit 1
    fi

    if [ ${#missing[@]} -ne 0 ]; then
        echo -e "${RED}Error: Missing required tools: ${missing[*]}${NC}"
        exit 1
    fi
}

# Detect which Python file is the bot
detect_bot_file() {
    echo -e "${GREEN}Detecting bot file...${NC}"

    # Find Python files in root that look like bots
    local candidates=()
    for f in *.py; do
        [ -f "$f" ] || continue
        # Skip known non-bot files
        case "$f" in
            setup.py|conftest.py) continue ;;
        esac
        # Check if filename suggests a bot
        if echo "$f" | grep -qiE "(bot|trader|maker|trading)"; then
            candidates+=("$f")
        fi
    done

    if [ ${#candidates[@]} -eq 0 ]; then
        # No obvious bot files — list all root .py files
        for f in *.py; do
            [ -f "$f" ] || continue
            case "$f" in
                setup.py|conftest.py) continue ;;
            esac
            candidates+=("$f")
        done
    fi

    if [ ${#candidates[@]} -eq 0 ]; then
        echo -e "${RED}No Python bot files found in the current directory.${NC}"
        echo "Make sure you're in your bot's directory and have created a bot first."
        exit 1
    elif [ ${#candidates[@]} -eq 1 ]; then
        BOT_FILE="${candidates[0]}"
        read -p "Deploy ${BOT_FILE}? (Y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            echo "Aborting."
            exit 1
        fi
    else
        echo "Multiple Python files found. Which one is your bot?"
        echo ""
        local i=1
        for f in "${candidates[@]}"; do
            echo "  $i) $f"
            ((i++))
        done
        echo ""
        read -p "Enter number (1-${#candidates[@]}): " -r
        local idx=$((REPLY - 1))
        if [ "$idx" -lt 0 ] || [ "$idx" -ge "${#candidates[@]}" ]; then
            echo -e "${RED}Invalid selection.${NC}"
            exit 1
        fi
        BOT_FILE="${candidates[$idx]}"
    fi

    echo -e "${GREEN}Using bot file: ${BOT_FILE}${NC}"
}

# Generate Railway deployment configuration
generate_railway_config() {
    echo -e "${GREEN}Generating deployment config...${NC}"

    # Create requirements.txt — tells Railpack to install deps from pyproject.toml
    echo "." > requirements.txt
    echo "  Created requirements.txt"

    # Create main.py entry point — Railpack auto-detects this
    if [ "$BOT_FILE" = "main.py" ]; then
        echo "  Bot is already main.py — Railpack will find it automatically"
    else
        cat > main.py << EOF
import runpy
runpy.run_path("${BOT_FILE}", run_name="__main__")
EOF
        echo "  Created main.py (entry point for ${BOT_FILE})"
    fi

    # Create railway.toml — configures restart policy
    cat > railway.toml << EOF
[deploy]
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
EOF
    echo "  Created railway.toml"
}

# Login to Railway
railway_login() {
    echo ""
    echo -e "${GREEN}Logging into Railway...${NC}"
    echo ""

    # Use --browserless if not in an interactive terminal (e.g., running from Claude)
    if [ -t 0 ]; then
        echo "(This will open your browser for authentication)"
        echo ""
        railway login
    else
        echo "(Copy the URL below and open it in your browser)"
        echo ""
        railway login --browserless
    fi
}

# Create a Railway project
railway_init_project() {
    echo ""
    echo -e "${GREEN}Creating Railway project...${NC}"
    railway init --name "turbine-bot" 2>/dev/null || {
        echo -e "${YELLOW}Could not create project. Linking to existing project...${NC}"
        railway link
    }
}

# Push environment variables to Railway
push_env_vars() {
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}  Your environment variables will be pushed to Railway.${NC}"
    echo -e "${YELLOW}  They are encrypted at rest on Railway's servers.${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    # Parse .env file for our variables
    local private_key=""
    local api_key_id=""
    local api_private_key=""

    while IFS= read -r line; do
        # Skip comments and empty lines
        [[ "$line" =~ ^#.*$ ]] && continue
        [[ -z "$line" ]] && continue

        case "$line" in
            TURBINE_PRIVATE_KEY=*)
                private_key="${line#TURBINE_PRIVATE_KEY=}"
                ;;
            TURBINE_API_KEY_ID=*)
                api_key_id="${line#TURBINE_API_KEY_ID=}"
                ;;
            TURBINE_API_PRIVATE_KEY=*)
                api_private_key="${line#TURBINE_API_PRIVATE_KEY=}"
                ;;
        esac
    done < .env

    # Check if private key looks real
    if [ -z "$private_key" ] || [[ "$private_key" == *"your_private_key"* ]] || [[ "$private_key" == "0x..." ]]; then
        echo -e "${RED}Error: TURBINE_PRIVATE_KEY is not set in .env${NC}"
        echo "Add your Ethereum wallet private key to .env first."
        exit 1
    fi

    # Mask and show what we're pushing
    local masked_key="${private_key:0:6}...${private_key: -4}"
    echo "  TURBINE_PRIVATE_KEY = ${masked_key}"

    if [ -n "$api_key_id" ]; then
        local masked_api_id="${api_key_id:0:8}..."
        echo "  TURBINE_API_KEY_ID  = ${masked_api_id}"
    else
        echo -e "  TURBINE_API_KEY_ID  = ${YELLOW}(empty - will auto-register on first run)${NC}"
    fi

    if [ -n "$api_private_key" ]; then
        echo "  TURBINE_API_PRIVATE_KEY = (set)"
    else
        echo -e "  TURBINE_API_PRIVATE_KEY = ${YELLOW}(empty - will auto-register on first run)${NC}"
    fi

    # Warn about empty API credentials
    if [ -z "$api_key_id" ] || [ -z "$api_private_key" ]; then
        echo ""
        echo -e "${YELLOW}Tip: Run your bot locally first (python ${BOT_FILE}) to auto-generate${NC}"
        echo -e "${YELLOW}API credentials. Then they'll be saved to .env and deployed here.${NC}"
    fi

    echo ""
    read -p "Push these secrets to Railway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping environment variables. Set them manually in the Railway dashboard."
        return
    fi

    # Push each variable
    railway variables --set "TURBINE_PRIVATE_KEY=${private_key}"
    echo -e "  ${GREEN}✓${NC} TURBINE_PRIVATE_KEY"

    if [ -n "$api_key_id" ]; then
        railway variables --set "TURBINE_API_KEY_ID=${api_key_id}"
        echo -e "  ${GREEN}✓${NC} TURBINE_API_KEY_ID"
    fi

    if [ -n "$api_private_key" ]; then
        railway variables --set "TURBINE_API_PRIVATE_KEY=${api_private_key}"
        echo -e "  ${GREEN}✓${NC} TURBINE_API_PRIVATE_KEY"
    fi

    echo -e "${GREEN}Environment variables pushed.${NC}"
}

# Deploy to Railway
deploy() {
    echo ""
    echo -e "${GREEN}Deploying to Railway...${NC}"
    echo ""

    railway up --detach

    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  Deployment started!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "  Useful commands:"
    echo "    railway logs          # Stream bot logs"
    echo "    railway status        # Check deployment status"
    echo "    railway variables     # View environment variables"
    echo "    railway down          # Stop deployment"
    echo "    railway open          # Open Railway dashboard"
    echo ""
    echo -e "  ${YELLOW}Railway free tier: \$5 credit for 30 days, then \$1/month.${NC}"
    echo ""
}

# Main execution
main() {
    echo "Checking requirements..."
    check_requirements

    detect_bot_file

    generate_railway_config

    railway_login

    railway_init_project

    push_env_vars

    deploy
}

main
