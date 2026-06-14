---
name: dashboard
description: Open the prospect triage interface. Starts the local sink (browser <-> disk bridge) if it isn't running, then opens viewer/index.html in the default browser. Triage happens in the viewer (filter, expand, click "I applied" on each row); the chat catches the rest via /sweep.
allowed-tools: Bash
---

The user invoked `/dashboard`. They want the viewer open so they can
triage prospects.

## What you do

### Step 1 - Check if the local sink is already running

```bash
# The sink listens on a known port (configurable in config.json,
# default 7878). Quick check:
lsof -nP -iTCP:7878 -sTCP:LISTEN 2>/dev/null | grep -q LISTEN
echo "sink_running=$?"
```

If `sink_running=0`, the sink is already up. Skip to step 3.
If `sink_running=1`, start it.

### Step 2 - Start the local sink in the background

```bash
nohup python scripts/local_sink.py > sink.log 2>&1 &
echo "started sink, pid=$!"
```

Wait ~2 seconds, then verify:

```bash
sleep 2 && lsof -nP -iTCP:7878 -sTCP:LISTEN 2>/dev/null | head -3
```

If verification fails, tail `sink.log` and report the error.

### Step 3 - Open the viewer

```bash
# Mac:
open viewer/index.html

# If `open` isn't available (Linux), use:
# xdg-open viewer/index.html
```

The viewer is a single-file static HTML that fetches `../data/*.json`
and renders the triage interface. It connects to the local sink for
write actions (the "I applied" button on each prospect dual-writes via
`scripts/apply.py with-prospect-id`).

### Step 4 - Confirm to the user

```
Sink running on :7878. Viewer open.

Triage there:
  - Filter by state (new / shortlist / applied / skip)
  - Click "I applied" on a row -> dual-writes active.json + prospect state
  - Click "skip" on a row -> sets state=skip (won't resurface)
  - Click "details" -> shows the cached JD + analysis

When you're done, the only thing left is to /sweep periodically so
closures land automatically from rejection emails.
```

## What you do NOT do

- Do NOT kill an existing sink. Leave running sinks alone; just open
  the viewer.
- Do NOT auto-/sweep or auto-/fetch-jobs from this command. Those are
  separate commands the user runs intentionally.
- Do NOT navigate to a specific filter in the viewer; the viewer
  remembers the user's last filter from localStorage.

## Edge cases

- Port 7878 busy with something else (not the sink) -> tell the user,
  ask if they want to change the port in `config.json`
- viewer/index.html missing -> tell the user, suggest `git pull`
- `open` not available -> print the absolute path and tell them to
  open it manually
