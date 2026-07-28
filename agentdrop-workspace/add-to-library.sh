#!/bin/zsh
# Add a reel / short-video URL to the AgentDrop Library (~/AgentDrop-Workspace/reels/).
# Usage: ./add-to-library.sh "https://www.instagram.com/reel/XXXX/"
# Best-quality mp4 + caption sidecar, named by the platform id so it matches
# what ig-curate.py produces. Idempotent — already-added reels are skipped.
set -euo pipefail

URL="${1:?usage: add-to-library.sh <url>}"
WORKSPACE="$HOME/AgentDrop-Workspace"
REELS="$WORKSPACE/reels"
COOKIES="$WORKSPACE/.ig-cookies.txt"
mkdir -p "$REELS"

ARGS=()
if [[ "$URL" == *instagram.com* && -f "$COOKIES" ]]; then
    ARGS+=(--cookies "$COOKIES")
fi

# Instagram: yt-dlp's IG extractor breaks whenever Instagram changes their
# API, so go straight to the instagrapi-based fetcher for those links.
if [[ "$URL" == *instagram.com* ]]; then
    DEST=$("$WORKSPACE/.venv/bin/python" "$WORKSPACE/ig-fetch.py" "$URL")
    echo "added to library: $DEST"
    exit 0
fi

ID=$(yt-dlp "${ARGS[@]}" --no-warnings --print id --no-download "$URL" | head -1)
if [[ -z "$ID" ]]; then
    echo "couldn't resolve that URL" >&2
    exit 1
fi

DEST="$REELS/$ID.mp4"
if [[ -f "$DEST" ]]; then
    echo "already in library: $DEST"
    exit 0
fi

yt-dlp "${ARGS[@]}" --quiet --no-warnings -f "bv*+ba/b" \
    --merge-output-format mp4 -o "$DEST" "$URL"

if [[ ! -f "$REELS/$ID.txt" ]]; then
    yt-dlp "${ARGS[@]}" --no-warnings --no-download \
        --print "@%(uploader)s: %(description)s" "$URL" > "$REELS/$ID.txt" 2>/dev/null || true
fi

echo "added to library: $DEST"
