"""CLI-agnostic LLM caller.

Any LLM CLI works. The command is configured in config.json -> llm_cli:

    "llm_cli": {
      "command": "claude",
      "args": ["-p"],
      "prompt_via": "stdin",      // or "arg"
      "timeout_seconds": 300
    }

The prompt is sent on stdin by default; set prompt_via to "arg" to append it
as the last argument instead. The model's raw reply is returned from stdout.

Note: configure your CLI so its stdout is the plain model reply (e.g. `claude -p`,
NOT `claude -p --output-format json`). The scripts parse the model's text directly.
"""
import subprocess


def call_llm(prompt, cfg, timeout=None):
    """Run the configured LLM CLI with `prompt`. Return stdout (stripped).
    Raises RuntimeError with an actionable message on any failure."""
    spec = cfg.get("llm_cli", {}) or {}
    command = spec.get("command")
    if not command:
        raise RuntimeError(
            "config.llm_cli.command is not set. Point it at your LLM CLI "
            "(e.g. \"claude\", \"ollama\", an openai CLI)."
        )
    args = list(spec.get("args", []) or [])
    prompt_via = spec.get("prompt_via", "stdin")
    timeout = timeout or int(spec.get("timeout_seconds", 300) or 300)

    argv = [command] + args
    stdin_data = None
    if prompt_via == "arg":
        argv = argv + [prompt]
    else:
        stdin_data = prompt

    try:
        result = subprocess.run(
            argv,
            input=stdin_data,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        raise RuntimeError(
            f"LLM CLI '{command}' not found on PATH. Install it or fix "
            f"config.llm_cli.command."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"LLM CLI '{command}' timed out after {timeout}s.")

    if result.returncode != 0:
        raise RuntimeError(
            f"LLM CLI '{command}' exited {result.returncode}. "
            f"STDERR: {(result.stderr or '').strip()[:500]}"
        )
    out = (result.stdout or "").strip()
    if not out:
        raise RuntimeError(f"LLM CLI '{command}' returned empty stdout.")
    return out
