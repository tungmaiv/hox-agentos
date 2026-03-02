---
status: complete
phase: 05-scheduler-and-channels
source: [05-01-SUMMARY.md, 05-02-SUMMARY.md, 05-03-SUMMARY.md, 05-04-SUMMARY.md, 05-05-SUMMARY.md, 05-06-SUMMARY.md]
started: 2026-02-28T22:30:00Z
updated: 2026-02-28T22:45:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

[testing complete]

## Tests

### 1. Channel Linking page renders with 3 channel cards
expected: Visit http://localhost:3000/settings, click "Channel Linking" card. Three channel cards render (Telegram, WhatsApp, MS Teams) each with a toggle switch. Toggles default to disabled for new users (no prior localStorage).
result: pass

### 2. Pairing code generation with countdown timer
expected: Enable a channel toggle, click "Link" button. A 6-character pairing code appears with a "Code expires in 10:00" countdown that decrements in real-time every second. When countdown reaches 0, it shows "Code expired. Generate a new one."
result: pass

### 3. Copy pairing code to clipboard
expected: With a pairing code visible, click the copy button next to it. The code is copied to clipboard and a green checkmark icon appears for 2 seconds before reverting to the copy icon.
result: pass

### 4. Telegram bot username displayed on card
expected: With Telegram sidecar running (docker), the Telegram card shows the bot's @username fetched from the sidecar /info endpoint (e.g., "Bot: @YourBotName"). If sidecar is not running, card still renders gracefully without bot info.
result: pass

### 5. Setup guide sections per channel
expected: Each channel card has a collapsible "Setup Guide" section. Expanding it shows two sub-sections: "AgentOS Configuration" (env vars needed) and "Platform Setup" (external platform steps). Telegram guide dynamically shows the real bot username if available.
result: pass

### 6. Telegram pairing flow end-to-end
expected: Generate a pairing code on the web UI, then send "/pair CODE" to the Telegram bot. The web UI detects the pairing within a few seconds (polling) and shows the linked account. The Telegram card displays "Linked as [chat_id]".
result: pass

### 7. Telegram message and agent response
expected: After pairing, send a text message to the Telegram bot. The bot shows a typing indicator, then replies with the agent's response. The response is formatted as readable text (not raw JSON).
result: pass

### 8. Unlink a channel account
expected: On a linked channel card, click "Unlink". A confirmation dialog appears. Confirming removes the linked account, card reverts to "Link" state with the toggle still enabled.
result: pass

### 9. Channel auto-enable toggle for linked accounts
expected: If you already have a linked account for a channel (e.g., Telegram), the toggle for that channel is automatically enabled on page load even without prior localStorage state.
result: pass

### 10. Backend test suite passes (292 tests)
expected: Run `cd backend && PYTHONPATH=. .venv/bin/pytest tests/ -q` — all 292 tests pass with 0 failures.
result: pass

### 11. Frontend build passes (TypeScript strict)
expected: Run `cd frontend && pnpm run build` — exits with code 0, all routes compile including /settings/channels.
result: pass

## Summary

total: 11
passed: 11
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
