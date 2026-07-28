# DESIGN.md

name: nate-default
colors:
  bg: "#0b0d12"
  bg2: "#11141c"
  ink: "#e8eaf2"
  ink-dim: "#9aa0b4"
  ink-faint: "#7b829b"
  mint: "#9fe8c9"
  lav: "#c3b8f5"
  peach: "#f5c9a8"
  rose: "#f2a9c4"
  sky: "#a8d8f5"
  glass: "rgba(255, 255, 255, 0.045)"
  glass-brd: "rgba(255, 255, 255, 0.09)"

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
