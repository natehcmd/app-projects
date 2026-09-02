#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "→ Hands AI — Xcode project setup"

if ! command -v xcodegen >/dev/null 2>&1; then
  echo "→ Installing xcodegen via Homebrew..."
  if ! command -v brew >/dev/null 2>&1; then
    echo "✗ Homebrew not found. Install from https://brew.sh first, then re-run."
    exit 1
  fi
  brew install xcodegen
fi

echo "→ Generating HandsAI.xcodeproj..."
xcodegen generate

echo "→ Opening in Xcode..."
open HandsAI.xcodeproj

echo "✓ Done. In Xcode: pick the HandsAI scheme and hit ⌘R to run."
