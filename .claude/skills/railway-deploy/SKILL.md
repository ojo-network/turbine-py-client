---
name: railway-deploy
description: Deploy a Turbine trading bot to Railway for 24/7 cloud operation. Use after creating a bot with /create-bot.
disable-model-invocation: false
argument-hint: "[bot-filename]"
---

# Turbine Bot - Railway Deployment (via GitHub)

You are helping a user deploy their Turbine trading bot to Railway for 24/7 cloud operation.

This skill uses GitHub for deployment — Railway's GitHub integration auto-deploys when a repo is connected. No Railway CLI needed.

Railway's free tier includes a $5 credit for 30 days — plenty for a lightweight Python trading bot.

## Step 0: Check Prerequisites

Run these checks:

```bash
# Check gh CLI
command -v gh && gh --version || echo "GH_NOT_FOUND"

# Check gh auth status
gh auth status 2>&1 || echo "GH_NOT_AUTHENTICATED"

# Check git
command -v git && git --version || echo "GIT_NOT_FOUND"

# Check for .env
ls -la .env 2>/dev/null || echo "NO_ENV_FILE"

# Check for bot Python files in root (exclude examples/, tests/, turbine_client/)
ls *.py 2>/dev/null || echo "NO_PY_FILES"
```

**If `gh` CLI is not found:**
Tell the user to install it:
```
GitHub CLI (gh) is required for deployment. Install it:
  brew install gh

Then authenticate:
  gh auth login
```
STOP here.

**If `gh` is not authenticated:**
Tell the user:
```
You need to log in to GitHub first:
  gh auth login
```
STOP here.

**If `git` is not found:**
Tell the user to install it:
```
Git is required. Install it:
  brew install git
```
STOP here.

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

## Step 3: Prepare for Deployment

Create a `.gitignore` if one doesn't already exist (or append to it if it does). Make sure these entries are present:

```
.env
__pycache__/
*.pyc
.venv/
venv/
```

**IMPORTANT:** Never commit `.env` — it contains private keys.

Create a `Procfile` as an alternative entry point for Railway:

```
web: python main.py
```

Stage and commit the bot file and all config files:

```bash
git add {BOT_FILE} requirements.txt main.py railway.toml .gitignore Procfile
git commit -m "Add Turbine bot for Railway deployment"
```

If there are other project files needed (like `pyproject.toml`, `turbine_client/`, etc.), include them too. Use your judgment — commit everything needed to run the bot, but never `.env`.

## Step 4: Create GitHub Repo and Push

Check the current git state:

```bash
# Are we in a git repo?
git rev-parse --is-inside-work-tree 2>/dev/null || echo "NOT_A_GIT_REPO"

# Does a remote named 'origin' exist?
git remote get-url origin 2>/dev/null || echo "NO_REMOTE"
```

**If not in a git repo:**
```bash
git init
git add {BOT_FILE} requirements.txt main.py railway.toml .gitignore Procfile
git commit -m "Add Turbine bot for Railway deployment"
```

**If a remote `origin` already exists:**
Just push:
```bash
git push origin HEAD
```

**If no remote exists:**
Create a private GitHub repo and push in one step:
```bash
gh repo create turbine-bot --private --source=. --push
```

Verify the push succeeded by checking the exit code. If it fails, show the error and STOP.

After a successful push, get the repo URL to show the user:
```bash
gh repo view --json url -q '.url'
```

## Step 5: Guide User to Connect Railway

Now tell the user to connect their GitHub repo to Railway. Print this clearly:

```
Your code is pushed to GitHub. Now connect it to Railway:

1. Go to https://railway.com/new
2. Click "Deploy from GitHub repo"
3. Select the repo: {REPO_NAME}
4. Railway will auto-deploy immediately

After the service is created, add your environment variables:

1. Click on the service in your Railway dashboard
2. Go to the "Variables" tab
3. Add the variables listed below
```

Then read the `.env` file and print the variables the user needs to set, with values masked for security. Show first 6 and last 4 characters of secret values:

| Variable | Value |
|----------|-------|
| `TURBINE_PRIVATE_KEY` | `0x1234...abcd` |
| `TURBINE_API_KEY_ID` | `abc123...wxyz` |
| `TURBINE_API_PRIVATE_KEY` | `secret...last4` |
| `CHAIN_ID` | `137` (show full value — not secret) |
| `TURBINE_HOST` | `https://api.turbinefi.com` (show full value — not secret) |

**IMPORTANT: Security handling:**
- Never print full private key values. Mask them: show first 6 and last 4 characters only.
- `CHAIN_ID` and `TURBINE_HOST` are not secrets — show them in full.

Then tell the user:
```
Copy each value from your .env file and paste it into Railway's Variables tab.

Tip: You can also click "Raw Editor" in Railway and paste all variables at once
in KEY=VALUE format.
```

**If API credentials are empty:**
Tell the user:
```
Your TURBINE_API_KEY_ID and TURBINE_API_PRIVATE_KEY are empty.
The bot auto-generates these on first run and saves them to .env.

Recommended: Run your bot locally first to generate credentials:
  python {BOT_FILE}

Then copy the generated values from .env into Railway's Variables tab.

Or deploy now — the bot will auto-register on Railway, but you'll need to
copy the credentials from Railway's deployment logs into the Variables tab
to persist them across redeployments.
```

Use `AskUserQuestion`:
- "API credentials are empty. What would you like to do?"
- Options: "Run bot locally first (Recommended)" / "Deploy without them"

If they choose to run locally, tell them to run `python {BOT_FILE}`, wait for it to register, then run `/railway-deploy` again. STOP here.

## Step 6: Success Message

Tell the user:

```
Your bot is ready for Railway deployment!

What you've done:
  - Bot code pushed to GitHub
  - Connect the repo on Railway to start your bot

Future deploys are automatic:
  git add . && git commit -m "update bot" && git push
  Railway redeploys automatically on every push.

Useful links:
  Railway Dashboard  -> https://railway.com/dashboard
  Railway Logs       -> Click your service -> "Logs" tab
  GitHub Repo        -> {REPO_URL}

Railway free tier: $5 credit for 30 days, then $1/month.
```
