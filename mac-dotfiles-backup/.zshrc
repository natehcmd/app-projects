# ─────────────────────────────────────────────
# PATH
# ─────────────────────────────────────────────
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
export PATH="$HOME/.npm-global/bin:$PATH"

# ─────────────────────────────────────────────
# MODE SWITCHER
# ─────────────────────────────────────────────
alias mode="bash $HOME/.modes/mode.sh"
alias makeitone="bash $HOME/.modes/make_it_one.sh"

# ─────────────────────────────────────────────
# OLD MAC — uses ~/.ssh/config host aliases
# ─────────────────────────────────────────────
alias oldmac='ssh oldmac'
alias oldmac-remote='ssh oldmac-remote'
alias oldmac-ping='ping -c 3 192.168.2.1'
alias n8n-open='open http://192.168.2.1:5678'
alias n8n-log='ssh oldmac "tail -f /tmp/n8n.log"'

sendfile() {
  [[ -z "$1" ]] && echo "usage: sendfile <file>" && return 1
  scp "$1" oldmac:~/Desktop/
}

oldmac-run() {
  [[ -z "$1" ]] && echo "usage: oldmac-run <command>" && return 1
  ssh oldmac "$1"
}

# ─────────────────────────────────────────────
# GMAIL SORTER
# ─────────────────────────────────────────────
alias gmail-sort='node $HOME/Projects/AI/gmail-sorter-v5.2/src/sort-now.mjs'

# JAX AGENT
alias jax='/opt/homebrew/bin/node /Users/natehoward/Projects/AI/myagent/agent.mjs'

# AI MASTER
alias aimasterapp='node $HOME/Projects/ai-master-app/server.mjs'
alias aimaster='open $HOME/Projects/ai-master-app/dist/mac-arm64/AI\ Master.app'

# DAISY MAC (AI assistant account on old Mac)
alias daisy='bash $HOME/Projects/daisy-mac/boot.sh'

# YOLO CLAUDE
alias claude='claude --dangerously-skip-permissions'
alias claude-yolo='claude --dangerously-skip-permissions'

# YOLO AGY
alias agy='agy --dangerously-skip-permissions'

# YOLO CODEX
alias codex='codex --yolo'
yolo() {
  codex -C /Users/natehoward -s danger-full-access -a never "$@"
}

# Local AI tools
alias aider="~/local-ai-tools/bin/aider"
alias mlx_lm="~/local-ai-tools/bin/mlx_lm"

# Added by LM Studio CLI (lms)
export PATH="$PATH:/Users/natehoward/.lmstudio/bin"
# End of LM Studio CLI section


# claude-local: run Claude Code against local Ollama models (no API costs, fully offline)
# Usage: claude-local              -> uses qwen2.5-coder:32b
#        claude-local devstral     -> any model from `ollama list`
# Note: for long agentic sessions, restart the Ollama server with OLLAMA_CONTEXT_LENGTH=65536
claude-local() {
  local model="${1:-qwen2.5-coder:32b}"
  [ $# -gt 0 ] && shift
  ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_BASE_URL=http://localhost:11434 claude --model "$model" "$@"
}


# Added by Antigravity CLI installer
export PATH="/Users/natehoward/.local/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"

# Agent Safeguard
alias safeguard='/Users/natehoward/scripts/agent-safeguard.sh'

