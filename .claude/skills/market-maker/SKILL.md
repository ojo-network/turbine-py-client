---
name: market-maker
description: "[Replaced] Use /setup for onboarding or /create-bot for bot generation."
---

# /market-maker has been replaced

This skill has been split into two focused skills:

1. **`/setup`** — Environment setup, wallet creation, .env configuration, funding guidance. Run this first if you're new.
2. **`/create-bot`** — Algorithm selection and bot code generation. Run this when you're ready to build a trading bot.

**What to do now:**

- If the user needs to set up their environment → tell them to run `/setup`
- If the user is already set up and wants to create a bot → tell them to run `/create-bot`
- If you're unsure → run `/setup`, it will detect what's already done and skip to what's needed

Do NOT attempt to generate bot code or walk through setup from this skill. Redirect to the appropriate skill above.
