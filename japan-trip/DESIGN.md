# DESIGN.md

name: japan-trip (black / red / cream / white)
colors:
  bg: "#100c0b"        # near-black, warm sumi-ink undertone
  bg2: "#1a1412"        # panel background
  ink: "#f4ece0"        # cream text
  ink-dim: "#c7b8a8"
  ink-faint: "#93826f"
  mint: "#d94a3b"        # vermillion (torii red) — primary accent
  lav: "#8c1c2b"        # deep maroon — secondary accent
  peach: "#f0e4d0"        # cream — used for soft highlights
  rose: "#e6413a"        # bright red — used for emphasis/alerts
  sky: "#ffffff"        # white — used for highest-contrast highlights
  glass: "rgba(255, 255, 255, 0.045)"
  glass-brd: "rgba(244, 236, 224, 0.12)"

typography:
  base: '"Avenir Next", -apple-system, "SF Pro Text", sans-serif'
  mono: '"SF Mono", Menlo, monospace'

spacing:
  r: "18px"
  shadow: "0 8px 32px rgba(0, 0, 0, 0.35)"

components:
  Orb Background: large blurred radial gradients in mint/lav/rose on the body.
  Glass Cards: background: var(--glass); border: 1px solid var(--glass-brd); backdrop-filter: blur(18px); border-radius: var(--r); box-shadow: var(--shadow);
  Primary Buttons: linear-gradient(135deg, var(--mint), #6fd3a8) with dark text (#0b2018).
  Pills: fully rounded borders with soft glass background.
