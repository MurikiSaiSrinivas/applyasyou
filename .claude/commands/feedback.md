---
name: feedback
description: Send a free-form feedback message to the applyasyou maintainer. Anonymous. Use whenever you want to flag what felt off in the workspace -- a confusing step, a bad output, a missing feature.
allowed-tools: Bash
---

The user invoked `/feedback`. They want to send an anonymous note to the
maintainer of this workspace.

## What you do

1. **If they typed a message with the command** (e.g. `/feedback the
   email-writer keeps adding em dashes`), use that as the message text.
   Skip to step 3.

2. **If they typed `/feedback` alone**, ask them one short question and
   wait for their reply:

   > What broke or annoyed you? Free-form is fine.

   Their reply is the message text.

3. **Check that feedback is enabled.** Run:

   ```bash
   python scripts/feedback_event.py status
   ```

   Parse the JSON output. If `feedback_enabled` is `false`, tell the user:

   > Feedback opt-out is on, so nothing was sent. If you want to opt in,
   > delete `~/.applyasyou/feedback_disabled` and re-run onboarding.

   Stop.

4. **Send the event.** Pass the message via `--message`. The script
   handles validation, transport, and never blocks user flow.

   ```bash
   python scripts/feedback_event.py manual manual manual --message "<their message>"
   ```

   (The repeated `manual manual manual` are the agent name, trigger_reason,
   and event_type — all literally `"manual"` for slash-command-initiated
   feedback.)

5. **Confirm in one warm line:**

   > Sent. Thanks for taking the time -- this is how the tool gets sharper.

   No flair. No follow-up questions.

## Rules

- NEVER include the user's name, email, JD text, resume content, or
  anything they didn't explicitly type for this feedback message. The
  message field is the only place free-form text goes.
- NEVER send the event if `feedback_enabled` is false. Always check status
  first.
- NEVER fail the user-facing flow if the POST fails. The script returns
  exit code 0 either way; a silent line goes to stderr. Just confirm.
- If the user's message is over 2000 chars, truncate it server-side
  (the table has a hard length check). Don't pre-truncate in the slash
  command -- the server's the source of truth.
