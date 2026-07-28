# Product

## Register

product

## Users

Nate — a solo power user running many parallel Claude/agent terminal sessions across three machines (Mac, Windows, Daisy). While deep in multi-agent work he loses track of which terminal is doing what. He needs a fast, glanceable board he can update in seconds without leaving flow.

## Product Purpose

Agent Deck is a local, single-file tracker for terminal/agent sessions. Each agent gets a name, a role ("what it does"), a color, a status, and a home machine. Agents appear both as a list and as an interactive graph where related agents can be linked (e.g. "orchestrator → worker", "generator → reviewer"). Success: at any moment Nate can look at the graph and know what every terminal is doing and how they relate.

## Brand Personality

Calm, capable, quietly playful. Follows the nate-default style system: dark-first, pastel accents, glass surfaces, subtle motion. The tool disappears into the task.

## Anti-references

- Enterprise dashboard clutter (Grafana-style wall of panels)
- SaaS hero-metric cards and gradient decoration
- Anything requiring a server, build step, or account

## Design Principles

1. **Two-second updates** — adding or editing an agent must be faster than losing your train of thought.
2. **The graph is the truth** — spatial layout and links carry meaning; color codes at a glance.
3. **Local and durable** — localStorage persistence, JSON export/import, zero dependencies.
4. **Familiar affordances** — standard drag, click-to-select, keyboard delete; no invented interactions.

## Accessibility & Inclusion

Body text ≥ 4.5:1 on dark surfaces. Status conveyed by dot + label, never color alone. Reduced-motion alternative for all animation. Full keyboard access for forms.
