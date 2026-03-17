---
name: locus-deploy
description: Deploy a Turbine trading bot to Locus for 24/7 cloud operation. Use after creating a bot with /create-bot.
disable-model-invocation: false
argument-hint: "[bot-filename]"
---

# Turbine Bot — Locus Deployment

You are helping a user deploy their Turbine trading bot to Locus for 24/7 cloud operation.

Locus is a container platform that deploys services via a REST API. Each service costs $0.25/month from workspace credits (new accounts start with $1.00). Services get an auto-subdomain at `svc-{id}.buildwithlocus.com` with HTTPS.

**Base URL:** `https://api.buildwithlocus.com/v1`

**Important:** The trading bot is a long-running Python process, not a web server. Locus requires a health endpoint on port 8080, so we create a lightweight wrapper that runs the bot as a subprocess and exposes a `/health` endpoint.

---

## Step 0: Check Prerequisites

Run these checks:

```bash
# Check for Locus API key
(test -f ~/.config/locus/credentials.json && cat ~/.config/locus/credentials.json | python3 -c "import sys,json; print('LOCUS_KEY:', json.load(sys.stdin).get('apiKey','NOT_SET'))" 2>/dev/null) || echo "LOCUS_KEY: NO_CREDENTIALS_FILE"
echo "LOCUS_ENV_KEY: ${LOCUS_API_KEY:-NOT_SET}"

# Check for .env
test -f .env && grep -q "TURBINE_PRIVATE_KEY=0x" .env && echo "ENV: OK" || echo "ENV: MISSING"

# Check for bot Python files in root (exclude examples/, tests/, turbine_client/)
ls *.py 2>/dev/null | grep -v setup.py | grep -v conftest.py || echo "NO_PY_FILES"

# Check for jq (needed for JSON parsing)
command -v jq && echo "JQ: OK" || echo "JQ: NOT_FOUND"

# Check for git
command -v git && echo "GIT: OK" || echo "GIT: NOT_FOUND"
```

**If jq is not found:**
Install it automatically:
1. If `brew` is available: `brew install jq`
2. Else if `apt` is available: `sudo apt-get install -y jq`
3. Else: Tell the user to install jq manually and STOP.

**If .env is not found:**
Tell the user to get set up first:
```
No .env file found. Run /setup first to configure your environment,
then /create-bot to generate a trading bot.
```
STOP here.

**If no Locus API key is found** (neither in `~/.config/locus/credentials.json` nor in `LOCUS_API_KEY` environment variable):

Tell the user:
```
No Locus API key found. You need a `claw_` API key to deploy.

Sign up for a Locus wallet at: https://paywithlocus.com

Once you have your API key, save it so I can use it:

Option 1 — Environment variable:
  export LOCUS_API_KEY=claw_your_key_here

Option 2 — Credentials file:
  mkdir -p ~/.config/locus
  echo '{"apiKey":"claw_your_key_here"}' > ~/.config/locus/credentials.json
```

Use `AskUserQuestion`:
- "Do you have a Locus API key?"
- Options: "Yes, let me set it up" / "No, I need to sign up"

If they need to sign up, give them the URL and STOP. If they have a key, wait for them to set it, then re-check.

**Base URL:** Always use `https://api.buildwithlocus.com/v1` for all API calls. All `claw_` keys (including those with `_dev_` in the name) work against the production API.

---

## Step 1: Identify the Bot File

If the user passed an argument (e.g., `/locus-deploy my_bot.py`), use that filename.

Otherwise, look at the Python files in the project root. Find files matching bot patterns (`*bot*`, `*trader*`, `*maker*`, `*trading*`). Exclude `setup.py`, `conftest.py`, and files inside `examples/`, `tests/`, `turbine_client/`.

If there's exactly one candidate, confirm with the user using `AskUserQuestion`:
- "Which file should Locus run?" with the detected file as the recommended option

If there are multiple candidates, present them all as options.

If there are zero candidates, use `AskUserQuestion` with a text prompt asking for the filename.

Store the result as `BOT_FILE` for the remaining steps.

---

## Step 2: Generate Deployment Files

The trading bot is a long-running Python process that doesn't serve HTTP. Locus requires a health check endpoint on port 8080, so we create a wrapper.

Create these files using the Write tool:

**`locus_runner.py`** — A wrapper that runs the bot as a subprocess and exposes a `/health` endpoint on port 8080:

```python
"""
Locus deployment wrapper for Turbine trading bot.
Runs the bot as a subprocess and exposes a /health endpoint on port 8080.
"""
import subprocess
import sys
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

BOT_FILE = os.environ.get("BOT_FILE", "{BOT_FILE}")

class HealthHandler(BaseHTTPRequestHandler):
    bot_process = None

    def do_GET(self):
        if self.path == "/health":
            if HealthHandler.bot_process and HealthHandler.bot_process.poll() is None:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
            else:
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"bot not running")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress health check logs

def run_bot():
    """Run the trading bot as a subprocess, streaming output."""
    proc = subprocess.Popen(
        [sys.executable, BOT_FILE],
        stdout=sys.stdout,
        stderr=sys.stderr,
        env=os.environ.copy(),
    )
    HealthHandler.bot_process = proc
    proc.wait()
    print(f"Bot process exited with code {proc.returncode}", flush=True)
    if proc.returncode != 0:
        sys.exit(proc.returncode)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))

    # Start health server in background thread
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    health_thread = threading.Thread(target=server.serve_forever, daemon=True)
    health_thread.start()
    print(f"Health endpoint listening on port {port}", flush=True)

    # Run the bot in the main thread
    run_bot()
```

Replace `{BOT_FILE}` with the actual bot filename.

**`Dockerfile`** — Container image for the bot:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (wget needed for Locus health checks on Alpine,
# but slim is Debian-based so we're fine)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for layer caching
COPY pyproject.toml ./
COPY turbine_client/ ./turbine_client/

# Install the SDK and dependencies
RUN pip install --no-cache-dir -e .

# Copy bot file and runner
COPY {BOT_FILE} ./
COPY locus_runner.py ./

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Locus injects PORT=8080 automatically
CMD ["python", "locus_runner.py"]
```

Replace `{BOT_FILE}` with the actual bot filename.

Tell the user what you created and why:
- `locus_runner.py` wraps the trading bot with a health endpoint on port 8080 — Locus needs this to know your bot is alive
- `Dockerfile` packages everything into a container — Python, the SDK, and the bot

---

## Step 3: Authenticate with Locus

Read the API key from whichever source was found in Step 0 (`~/.config/locus/credentials.json` or `LOCUS_API_KEY` env var).

**IMPORTANT: Never print the full API key.** Mask it: show first 8 and last 4 characters only.

Exchange the API key for a JWT token:

```bash
BASE_URL="https://api.buildwithlocus.com/v1"
LOCUS_API_KEY="claw_..."  # read from credentials

TOKEN=$(curl -s -X POST $BASE_URL/auth/exchange \
  -H "Content-Type: application/json" \
  -d '{"apiKey":"'"$LOCUS_API_KEY"'"}' | jq -r '.token')

# Save token for subsequent calls
echo $TOKEN > /tmp/locus-token.txt
echo "Authenticated with Locus"
```

If the token exchange fails (empty token, error response), show the error and STOP. Common issues:
- Invalid API key — double-check the `claw_` key

**Check billing balance:**

```bash
TOKEN=$(cat /tmp/locus-token.txt)
curl -s -H "Authorization: Bearer $TOKEN" \
  $BASE_URL/billing/balance | jq '{creditBalance, totalServices, status}'
```

If `creditBalance` < 0.25, tell the user:
```
Insufficient Locus credits. Each service costs $0.25/month.
Add credits at https://paywithlocus.com
```
STOP here.

Tell the user: "Authenticated with Locus. Credit balance: $X.XX"

---

## Step 4: Create Project, Environment, and Service

Run these API calls sequentially, communicating each step to the user:

**Create a project:**

```bash
TOKEN=$(cat /tmp/locus-token.txt)

PROJECT=$(curl -s -X POST $BASE_URL/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "turbine-bot", "description": "Turbine prediction market trading bot"}')

PROJECT_ID=$(echo $PROJECT | jq -r '.id')
echo "Project ID: $PROJECT_ID"
```

If the project creation fails, check the error. If a project named "turbine-bot" already exists, list projects and ask the user whether to reuse it or create a new one with a different name.

**Create an environment:**

```bash
ENV=$(curl -s -X POST $BASE_URL/projects/$PROJECT_ID/environments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "production", "type": "production"}')

ENV_ID=$(echo $ENV | jq -r '.id')
echo "Environment ID: $ENV_ID"
```

**Create a service:**

```bash
SERVICE=$(curl -s -X POST $BASE_URL/services \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "projectId": "'"$PROJECT_ID"'",
    "environmentId": "'"$ENV_ID"'",
    "name": "trading-bot",
    "source": { "type": "s3" },
    "buildConfig": {
      "method": "dockerfile",
      "dockerfile": "Dockerfile"
    },
    "runtime": {
      "port": 8080,
      "cpu": 256,
      "memory": 512,
      "minInstances": 1,
      "maxInstances": 1
    },
    "healthCheckPath": "/health"
  }')

SERVICE_ID=$(echo $SERVICE | jq -r '.id')
SERVICE_URL=$(echo $SERVICE | jq -r '.url')
echo "Service ID: $SERVICE_ID"
echo "Service URL: $SERVICE_URL"
```

Tell the user:
```
Project created: turbine-bot
Environment: production
Service: trading-bot
URL (once deployed): {SERVICE_URL}
```

---

## Step 5: Set Environment Variables

Read the `.env` file to extract the Turbine credentials:
- `TURBINE_PRIVATE_KEY`
- `TURBINE_API_KEY_ID`
- `TURBINE_API_PRIVATE_KEY`
- `CHAIN_ID`
- `TURBINE_HOST`

Also set `BOT_FILE` so the runner knows which file to execute.

**IMPORTANT: Security handling:**
- Never print raw private key values. Mask them: show first 6 and last 4 characters only.
- Before pushing, tell the user: "Your credentials will be stored as encrypted environment variables on Locus."

Use `AskUserQuestion` to confirm before pushing:
- "Push your Turbine credentials to Locus? They will be encrypted at rest."
- Options: "Yes, push secrets" / "No, I'll set them manually"

If the user approves:

```bash
TOKEN=$(cat /tmp/locus-token.txt)

curl -s -X PUT \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "variables": {
      "TURBINE_PRIVATE_KEY": "<value>",
      "TURBINE_API_KEY_ID": "<value>",
      "TURBINE_API_PRIVATE_KEY": "<value>",
      "CHAIN_ID": "<value>",
      "TURBINE_HOST": "<value>",
      "BOT_FILE": "<BOT_FILE>"
    }
  }' \
  "$BASE_URL/variables/service/$SERVICE_ID"
```

**If API credentials are empty:**
Tell the user:
```
Your TURBINE_API_KEY_ID and TURBINE_API_PRIVATE_KEY are empty.
The bot auto-generates these on first run and saves them to .env.

Recommended: Run your bot locally first to generate credentials:
  python {BOT_FILE}

Then re-run /locus-deploy to push the full credentials.

Or deploy now — the bot will auto-register on Locus, but credentials
won't persist across redeployments. You can copy them from the logs later.
```

Use `AskUserQuestion`:
- "API credentials are empty. What would you like to do?"
- Options: "Run bot locally first (Recommended)" / "Deploy without them"

If they choose to run locally, tell them to run `python {BOT_FILE}`, wait for it to register, then run `/locus-deploy` again. STOP here.

---

## Step 6: Deploy via Git Push

Set up the Locus git remote and push the code.

**Get the workspace ID:**

```bash
TOKEN=$(cat /tmp/locus-token.txt)

WORKSPACE_ID=$(curl -s -H "Authorization: Bearer $TOKEN" \
  $BASE_URL/auth/whoami | jq -r '.workspaceId')

echo "Workspace ID: $WORKSPACE_ID"
```

**Add the Locus git remote:**

Check if a `locus` remote already exists first. If it does, update it. If not, add it.

```bash
# Remove existing locus remote if present
git remote remove locus 2>/dev/null

# Add fresh Locus remote
git remote add locus "https://x:${LOCUS_API_KEY}@git.buildwithlocus.com/${WORKSPACE_ID}/${PROJECT_ID}.git"
```

**Important:** The deployment files (`locus_runner.py`, `Dockerfile`) need to be committed before pushing. Create a temporary commit with these files:

```bash
git add locus_runner.py Dockerfile
git commit -m "Add Locus deployment files"
```

**Push to deploy:**

Tell the user: "Pushing code to Locus. This will upload the source and trigger a build. Builds typically take 3-7 minutes."

```bash
git push locus main
```

If the push fails:
- Authentication error → Check the API key
- Branch error → Try `git push locus HEAD:main` if on a different branch
- Remote error → Verify workspace and project IDs

After the push, note the deployment IDs from the push output.

---

## Step 7: Monitor Deployment

Poll the deployment status. Extract the deployment ID from the push output, or query the service's latest deployment:

```bash
TOKEN=$(cat /tmp/locus-token.txt)

# Get the latest deployment for the service
DEPLOYMENT_ID=$(curl -s -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/services/$SERVICE_ID/deployments" | jq -r '.deployments[0].id')

echo "Monitoring deployment: $DEPLOYMENT_ID"
```

Poll every 30 seconds until it reaches a terminal state:

```bash
TOKEN=$(cat /tmp/locus-token.txt)

STATUS=$(curl -s -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/deployments/$DEPLOYMENT_ID" | jq -r '.status')
echo "Status: $STATUS"
```

Keep the user informed at each check:
- `queued` → "Build is queued, waiting to start..."
- `building` → "Building Docker image from source..."
- `deploying` → "Container is starting, running health checks..."
- `healthy` → "Deployment is live!"
- `failed` → Check logs and report the error

**If deployment fails**, fetch the last logs:

```bash
TOKEN=$(cat /tmp/locus-token.txt)

curl -s -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/deployments/$DEPLOYMENT_ID" | jq '.lastLogs'
```

Common failure causes:
- **Health check timeout:** The `/health` endpoint didn't respond in time. Check that `locus_runner.py` is starting the health server before the bot.
- **Dependency install failed:** Missing packages in `pyproject.toml`.
- **Dockerfile error:** Check the build logs for syntax issues.

Help the user fix the issue and redeploy with another `git push locus main`.

**IMPORTANT:** After deployment reaches `healthy`, the public URL may return 503 for up to 60 seconds while service discovery registers the container. This is normal. Tell the user to wait before testing the URL.

---

## Step 8: Success Message

Once the deployment is `healthy`, tell the user:

```
Your bot is deployed to Locus and running 24/7!

Bot URL: {SERVICE_URL}
Health check: {SERVICE_URL}/health

The bot is now trading automatically — it'll rotate through markets
every 15 minutes, place trades, and claim winnings.

Useful commands:
  To check status:
    curl -s -H "Authorization: Bearer $TOKEN" \
      "{BASE_URL}/services/{SERVICE_ID}?include=runtime" | jq '.runtime_instances'

  To redeploy after changes:
    git add -A && git commit -m "Update bot" && git push locus main

  To check logs (if deployment fails):
    curl -s -H "Authorization: Bearer $TOKEN" \
      "{BASE_URL}/deployments/{DEPLOYMENT_ID}" | jq '.lastLogs'

  To set/update environment variables:
    curl -X PATCH -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"variables":{"KEY":"value"}}' \
      "{BASE_URL}/variables/service/{SERVICE_ID}"

Locus costs $0.25/month per service from your credit balance.

Track your bot's performance on the leaderboard:
  https://beta.turbinefi.com/leaderboard
```

---

## Redeployment

If the user wants to redeploy after making changes to their bot:

1. Make changes to the bot file
2. Commit the changes: `git add {BOT_FILE} && git commit -m "Update trading strategy"`
3. Push to Locus: `git push locus main`
4. Monitor the deployment as in Step 7

The service URL stays the same — Locus does a rolling update with zero downtime.

---

## Cleanup

If the user wants to stop the bot and clean up:

```bash
TOKEN=$(cat /tmp/locus-token.txt)

# Delete the service (stops the container)
curl -s -X DELETE -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/services/$SERVICE_ID"

# Optionally remove the git remote
git remote remove locus

# Optionally remove deployment files
rm -f locus_runner.py Dockerfile
git commit -am "Remove Locus deployment files"
```

Tell the user this stops the bot and removes the service. The project can be reused later if they want to redeploy.
