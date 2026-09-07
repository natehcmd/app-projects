# SHARED — nate-default v2 tokens

One restrained token set for every app in this monorepo. Replaces the v1
"Premium Dark Glassmorphism" look (glass on everything + blurred orb backdrop +
5 saturated accents + neon glow) that the 2026-09-06 `sellable-vs-slop-audit`
scored **Tier 1 — premium cosplay** across all five audited apps.

- `nate-default-v2.css` — web (japan-trip, nfc-card, file-graph, Command Center)
- `NateDefaultV2.swift` — SwiftUI (net-worth, hands-ai-mac, Command Center native)

## v2 rules

1. **One accent.** Neutrals are one temperature (cool). Never pure `#000`.
2. **No orb backdrop. No neon glow** (`box-shadow: 0 0 Npx currentColor`).
3. **Glass only where elevation carries meaning** — not the default surface.
4. Real spacing scale: 4 / 8 / 12 / 16 / 24 / 32 / 48.
5. `tabular-nums` / `.monospacedDigit()` wherever digits line up.
6. Motion is feedback: 120–200ms toward rest. No decorative loops.
7. Every interactive element has a visible `:focus-visible` ring.

Per-app: override `--accent` / `ThemeV2.accent` only. japan-trip keeps its
vermillion; nothing else needs a custom hue.

## Migration status (2026-09-06)

| App | Done in `worktree-harden-apps` | Left |
|---|---|---|
| japan-trip | 100dvh, flat buttons, empty-copy | adopt v2 palette; rename mislabelled `--mint`/`--lav` vars (hold red) |
| nfc-card | favicon+OG+description, system font, focus ring, "Saved ✓", flat gold btn, removed `maximum-scale=1` | — |
| file-graph | favicon, 100dvh, designed empty state, backend-error toast | stop the `requestAnimationFrame` loop when the graph settles (needs wake() on mousedown/wheel/expand/search/mindBtn) |
| net-worth | `tnum()` helper + steering note | swap to `NateDefaultV2.swift`, `.monospacedDigit()` on currency, build + re-audit states |
| Command Center (mission-control) | done on the live tree, not here | see that repo |
