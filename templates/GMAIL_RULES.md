# Gmail rules -- the safety contract

Hard rules for any agent using the Gmail MCP server in this workspace.
Treat them with the same weight as the ASK rule on resume docs. These
override default behavior. If a request is ambiguous, ask before acting.

---

## 1. Reading is allowed

Search threads, read messages, pull context for replies, summarize an
inbox slice -- all fine without asking.

## 2. NEVER read anything bank-related

No bank statements, no account balances, no transaction emails, and
especially no bank PDFs or attachments from any financial institution.

Signals that a thread is off-limits:
- A bank name in the sender (Chase, BoA, Wells Fargo, Citi, Discover,
  Amex, Capital One, credit unions, payment processors)
- Words like `statement`, `balance`, `transaction`, `payment`,
  `account activity`, `wire`, `transfer`, `deposit` in the subject of
  a financial sender
- PDF attachments from financial senders

If a bank thread appears in a search result, leave it alone. Do not
call `get_thread` on it. When in doubt whether something counts as
bank-related, skip and ask.

## 3. Drafting is allowed

Use `create_draft` freely when the user asks for a reply. Drafts live
in their Gmail; they review and click send themselves.

## 4. NEVER send an email without explicit permission for that specific message

A general "draft this" or "reply to so-and-so" is permission to draft,
not to send. Even if a send tool becomes available, do not call it
unless the user says "send it" (or equivalent) for that exact message.

## 5. Deletion is forbidden by default

Never delete a message, thread, label, or draft unless the user gives
an explicit delete command for that specific item. Do not infer delete
intent from cleanup-style phrasing or general housekeeping requests.
Always confirm before deleting, even when the user seems to imply it.

## 6. Labels

Creating, applying, or removing labels is allowed only when it directly
serves a task the user asked for (e.g., "label all the job-search
emails"). Do not reorganize their label system on your own initiative.

---

## Where these rules apply

- **The gmail-sweeper agent** (`.claude/agents/gmail-sweeper.md`):
  reads inbox, drafts follow-ups, NEVER sends or deletes.
- **The email-writer agent** (`.claude/agents/email-writer.md`):
  drafts emails to recipients the user explicitly named. NEVER sends.
- **The orchestrator** (this `CLAUDE.md`): when the user asks for an
  email-related action in chat, follow the rules above; if a request
  is ambiguous, ask.

## What the user-facing summary should look like

When you finish an email-related action, ALWAYS include a one-line
ack of what was actually done at the Gmail layer:
- "Drafted in your Gmail. ID: <draft_id>"
- "Read N threads, all match the rejection pattern"
- "Skipped 3 threads (bank rule)"

That way the user can audit. Silent operations on their inbox are a
trust violation -- always surface what you touched.
