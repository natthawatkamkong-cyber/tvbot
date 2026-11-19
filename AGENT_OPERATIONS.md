# Autonomous coding agent — activation and proof
Status: **NOT ACTIVE**. This document describes the acceptance gates; it is not evidence of execution.

## Confirmed repo baseline
- Existing security PR #1 changes: `.env.example`, `.github/workflows/webhook-tests.yml`, `.gitignore`, `SECURITY_SETUP.md`, `app.py`, `tests/test_webhook.py`.
- Historical CI run 43979829524 passed. This does not mean the agent is running.
- Preflight workflow is proposed in PR #3; scheduled GitHub Actions will not run from this feature branch until merged into the default branch.
- Exposed Telegram bot token must remain revoked. Do not reintroduce secrets.

## Operator activation gates
1. Select a hosted coding runner with documented authentication, model/API pricing and limits.
2. Obtain account connection and explicit approval if charges are possible; never assume approval.
3. Store credentials in encrypted GitHub secrets or environment-scoped credentials; never commit values.
4. Grant least-privilege GitHub permissions; no production credentials or live trading access.
5. Install agent job that reads a scoped GitHub issue, edits an isolated branch, runs tests, and creates a **draft** PR.
6. Set maximum runtime, budget, retries and concurrency; keep merge/deploy manual.
7. Prove a single benign task with a workflow run URL, commit SHA, passing tests and draft PR URL.
8. Prove a second run without an active ChatGPT conversation.
9. Publish an evidence-based state: RUNNING (active run URL), IDLE (enabled + last run), BLOCKED (missing prerequisite), FAILED (failed run logs). If not independently verifiable, UNKNOWN.

## Stop conditions
Never start paid API usage without owner approval. Never merge, deploy, send Telegram messages, execute live trades, or access MT5 credentials automatically.

## Current next action
Identify and configure an available runner/provider. Until it is actually configured and tested, **do not say the agent is running**.
