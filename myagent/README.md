# 🦞 Jax — Your Personal AI Agent

OpenClaw-inspired personal assistant running locally. Safe, private, yours.

## Quick Start

```bash
# 1. Add your API keys to config.json
#    - OpenAI key for GPT
#    - Gemini key for Google
#    - Your phone number for iMessage

# 2. Run the agent
node ~/Projects/myagent/agent.mjs
```

## Chat Commands

| Command | What it does |
|---------|-------------|
| `@claude <msg>` | Route to Claude |
| `@gpt <msg>` | Route to ChatGPT |
| `@gemini <msg>` | Route to Gemini |
| `/memory` | Show what Jax remembers |
| `/remember <fact>` | Save a fact |
| `/forget <word>` | Remove memories with that word |
| `/model claude\|gpt\|gemini` | Switch default |
| `/skills` | List installed skills |
| `/status` | Agent health check |
| `/clear` | Clear conversation history |
| `/help` | Show all commands |

## Safety

- Confirms before any action containing: delete, remove, send, post, publish, buy, pay
- All logs saved to `logs/agent.log`
- Memory stored as local markdown — you own it
- No data sent anywhere except your chosen AI API

## iMessage Setup

1. Set `iMessage.yourNumber` in `config.json` to your phone number (e.g. `"+19725550000"`)
2. Run the agent
3. Text yourself — Jax will reply

## Adding Skills

Drop a folder with a `SKILL.md` into `~/Projects/myagent/skills/`
Or Jax automatically picks up skills from `~/.claude/skills/` too.

## API Keys

Edit `config.json`:
```json
"gpt":    { "enabled": true, "apiKey": "sk-..." },
"gemini": { "enabled": true, "apiKey": "AIza..." }
```
