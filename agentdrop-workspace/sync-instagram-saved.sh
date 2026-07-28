#!/bin/zsh
# Syncs Nate's Instagram Saved collection into ~/AgentDrop-Workspace/instagram-saved/
# Login comes from Arc's Instagram session (cookies re-exported fresh on every run).

set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$(dirname "$0")"

echo "🔑 Refreshing Instagram cookies from Arc…"
/opt/homebrew/opt/instaloader/libexec/bin/python - << 'EOF'
import browser_cookie3, time, os
cj = browser_cookie3.arc(domain_name='instagram.com')
names = {c.name for c in cj}
if 'sessionid' not in names:
    raise SystemExit("❌ Not logged into Instagram in Arc — open instagram.com in Arc and log in first.")
path = os.path.expanduser("~/AgentDrop-Workspace/.ig-cookies.txt")
with open(path, "w") as f:
    f.write("# Netscape HTTP Cookie File\n")
    for c in cj:
        flag = "TRUE" if c.domain.startswith(".") else "FALSE"
        expires = str(int(c.expires or time.time() + 86400*365))
        f.write(f"{c.domain}\t{flag}\t{c.path}\t{'TRUE' if c.secure else 'FALSE'}\t{expires}\t{c.name}\t{c.value}\n")
os.chmod(path, 0o600)
EOF

echo "📥 Syncing saved posts…"
gallery-dl --cookies .ig-cookies.txt -D instagram-saved \
  "https://www.instagram.com/tech.review.nate/saved/all-posts/"

echo "🔍 Quality pass — upgrading any video below 1080p…"
for f in instagram-saved/*.mp4(N); do
  ID="${${f:t}%.mp4}"
  [[ "$ID" == *_* ]] && ID="${ID%%_*}"   # carousel items share the post id prefix
  WIDTH=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$f" 2>/dev/null || echo 0)
  HEIGHT=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$f" 2>/dev/null || echo 0)
  MINDIM=$(( WIDTH < HEIGHT ? WIDTH : HEIGHT ))
  if (( MINDIM > 0 && MINDIM < 1080 )); then
    SHORTCODE=$(python3 -c "
alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
n=int('$ID'); s=''
while n: s=alphabet[n%64]+s; n//=64
print(s)")
    echo "  ⬆️  ${f:t} (${WIDTH}x${HEIGHT}) → fetching HD…"
    if yt-dlp --quiet --no-warnings --cookies .ig-cookies.txt \
        -f "bv*+ba/b" --merge-output-format mp4 \
        -o "$f" --force-overwrites \
        "https://www.instagram.com/reel/$SHORTCODE/" 2>/dev/null; then
      NEWH=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$f" 2>/dev/null)
      echo "      now ${NEWH}p"
    else
      echo "      (HD not available or fetch failed — keeping original)"
    fi
    sleep 2
  fi
done

COUNT=$(ls instagram-saved | grep -cv '\.json' || true)
echo "✅ Done — $COUNT media files in $(pwd)/instagram-saved/"
