# proxy.py — run Claude Code against a local Ollama model

## Source

> @codewithpetergriffin: Most developers still think using Claude Code means
> paying for API credits. Not anymore. You can now run it locally with
> Ollama + open-source models like Qwen and get the same powerful coding
> workflow directly on your machine. No API costs. No usage limits. No cloud
> dependency.

No actual proxy/adapter code was shown in the reel — the concrete idea
(translate Claude Code's Anthropic API calls to a local Ollama model) is
real and implementable, so that's what was built.

## What it does

A tiny stdlib-only HTTP server that translates the Anthropic Messages API
(what the `claude` CLI speaks) into Ollama's `/api/chat` format, so you can
point Claude Code at any locally-running Ollama model instead of the cloud.
Supports both streaming and non-streaming requests.

## Verified working

Tested end-to-end on 2026-07-20 against a locally running Ollama with
`qwen2.5-coder:32b` — `/health` and `/v1/messages` both returned correct
Anthropic-shaped responses.

## Usage

```bash
ollama serve                      # if not already running
python3 proxy.py                  # defaults to qwen2.5-coder:32b

# in another terminal:
export ANTHROPIC_BASE_URL=http://localhost:8787
export ANTHROPIC_API_KEY=local-not-checked   # any non-empty string
claude
```

Override the model or port with env vars: `OLLAMA_MODEL`, `OLLAMA_URL`,
`PROXY_PORT`, `PROXY_HOST`. Defaults to `qwen2.5-coder:32b` since that's
the coding model already pulled on this Mac (`ollama list`).

## Status

**built = true**, verified working.
