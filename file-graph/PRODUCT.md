# Product

## Register

product

## Users

Nate (solo user) — power user on a Mac Studio-class machine, exploring his own
file system and controlling what local AIs can see. Used in short bursts:
find something by meaning, check what a folder contains, toggle AI access.

## Product Purpose

File Graph: a local knowledge graph of every file on the Mac with semantic
search, a visual graph explorer, and per-folder AI access control. The MCP
server gives Claude/other AIs file context; the app is the human's window and
control panel. Success = finding any file by meaning in seconds and trusting
the privacy toggles completely.

## Brand Personality

Calm, capable, private. Feels like a native Apple power tool — closer to
Raycast/Things than a web dashboard. Motion is physical (the graph itself
moves); chrome stays quiet.

## Anti-references

- Web-dashboard-in-a-window (Electron feel, dense chrome, web buttons)
- Neon "cyberpunk graph viz" aesthetics; sci-fi hacker green-on-black
- Over-decorated glassmorphism everywhere — glass is for floating panels only

## Design Principles

1. The graph is the hero — chrome recedes, data glows.
2. Privacy state is always legible: blocked = unmistakably marked, everywhere.
3. Native affordances only — standard macOS toolbar, menus, shortcuts.
4. Motion conveys physics and state, never decoration.
5. Instant: search-as-you-type, 60fps graph, no spinners mid-canvas.

## Accessibility & Inclusion

Dark-first but respects system Reduce Motion (damp the simulation, no camera
fly-ins). Node kind is encoded by color AND shape/label, not color alone.
Text ≥ 4.5:1 contrast on panels.
