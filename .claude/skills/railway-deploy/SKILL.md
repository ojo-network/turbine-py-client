---
name: railway-deploy
description: Deploy a Turbine trading bot to Railway for 24/7 cloud operation. Use after creating a bot with /create-bot.
disable-model-invocation: false
argument-hint: "[bot-filename]"
---

# Turbine Bot - Railway Deployment

You are helping a user deploy their Turbine trading bot to Railway for 24/7 cloud operation.

Railway's free tier includes a $5 credit for 30 days — plenty for a lightweight Python trading bot.

## Step 0: Check Prerequisites

Run these checks:

```bash
# Check Railway CLI
command -v railway && railway --version || echo "RAILWAY_NOT_FOUND"

# Check for .env
ls -la .env 2>/dev/null || echo "NO_ENV_FILE"

# Check for bot Python files in root (exclude examples/, tests/, turbine_client/)
ls *.py 2>/dev/null || echo "NO_PY_FILES"
```

**If Railway CLI is not found:**
Install it automatically. Try these in order:

1. If `brew` is available: `brew install railway`
2. Else if `npm` is available: `npm i -g @railway/cli`
3. Else: `bash <(curl -fsSL cli.new)`

After installing, verify with `command -v railway && railway --version`. If installation fails, show the manual install options and STOP.

**If .env is not found:**
Tell the user to get set up first:
```
No .env file found. Run /setup first to configure your environment,
then /create-bot to generate a trading bot.
```
STOP here.

## Step 1: Identify the Bot File

If the user passed an argument (e.g., `/railway-deploy my_bot.py`), use that filename.

Otherwise, look at the Python files in the project root. Find files matching bot patterns (`*bot*`, `*trader*`, `*maker*`, `*trading*`). Exclude `setup.py`, `conftest.py`, and files inside `examples/`, `tests/`, `turbine_client/`.

If there's exactly one candidate, confirm with the user using `AskUserQuestion`:
- "Which file should Railway run?" with the detected file as the recommended option

If there are multiple candidates, present them all as options.

If there are zero candidates, use `AskUserQuestion` with a text prompt asking for the filename.

Store the result as `BOT_FILE` for the remaining steps.

## Step 2: Generate Deployment Configuration

Create these files using the Write tool:

**`requirements.txt`** — Railpack looks for this to install dependencies. A single `.` tells pip to install the package and all its deps from `pyproject.toml`:

```
.
```

**`main.py`** — Railpack looks for this file as the entry point. If `BOT_FILE` is already `main.py`, skip this step. Otherwise create it:

```python
import runpy
runpy.run_path("{BOT_FILE}", run_name="__main__")
```

**`railway.toml`** — configures restart policy:

```toml
[deploy]
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

Tell the user what you created and why:
- `requirements.txt` tells Railpack to install the project's dependencies from `pyproject.toml`
- `main.py` is the entry point Railpack auto-detects — it just runs `{BOT_FILE}`
- `railway.toml` configures restart-on-crash behavior

## Step 3: Railway Login and Project Setup

Run these commands sequentially:

```bash
railway login --browserless
```

This prints a URL and pairing code. Tell the user to open the URL in their browser and enter the code. Wait for confirmation before proceeding.

Then create a project:

```bash
railway init --name "turbine-bot"
```

If `railway init` fails (e.g., project name taken), try:

```bash
railway link
```

This lets the user select an existing project.

## Step 4: Push Environment Variables

Read the `.env` file to extract the three Turbine credentials:
- `TURBINE_PRIVATE_KEY`
- `TURBINE_API_KEY_ID`
- `TURBINE_API_PRIVATE_KEY`

**IMPORTANT: Security handling:**
- Never print raw private key values. Mask them: show first 6 and last 4 characters only.
- Before pushing, tell the user: "Your credentials will be stored as encrypted environment variables on Railway."

Use `AskUserQuestion` to confirm before pushing:
- "Push your credentials to Railway? They will be encrypted at rest."
- Options: "Yes, push secrets" / "No, I'll set them manually"

If the user approves, run these commands:

```bash
railway variables --set "TURBINE_PRIVATE_KEY=<value>"
railway variables --set "TURBINE_API_KEY_ID=<value>"
railway variables --set "TURBINE_API_PRIVATE_KEY=<value>"
```

**If API credentials are empty:**
Tell the user:
```
Your TURBINE_API_KEY_ID and TURBINE_API_PRIVATE_KEY are empty.
The bot auto-generates these on first run and saves them to .env.

Recommended: Run your bot locally first to generate credentials:
  python {BOT_FILE}

Then re-run /railway-deploy to push the full credentials.

Or deploy now — the bot will auto-register on Railway, but credentials
won't persist across redeployments. You can copy them from the logs later:
  railway logs
```

Use `AskUserQuestion`:
- "API credentials are empty. What would you like to do?"
- Options: "Run bot locally first (Recommended)" / "Deploy without them"

If they choose to run locally, tell them to run `python {BOT_FILE}`, wait for it to register, then run `/railway-deploy` again. STOP here.

## Step 5: Deploy

Run the deployment:

```bash
railway up --detach
```

The `--detach` flag returns immediately instead of streaming logs.

## Step 6: Success Message

Tell the user:

```
Your bot is deployed to Railway!

Useful commands:
  railway logs          # Stream bot logs
  railway status        # Check deployment status
  railway variables     # View environment variables
  railway down          # Stop deployment
  railway open          # Open Railway dashboard

Railway free tier: $5 credit for 30 days, then $1/month.

To redeploy after making changes:
  railway up --detach
```
