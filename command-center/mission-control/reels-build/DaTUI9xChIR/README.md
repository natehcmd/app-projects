# Jarvis Command Assistant

## Source material — what was actually in the reel

The reel's caption/transcript (`@fatihmakes`) is self-promotional hype about a
personal project: a custom "Jarvis" AI assistant that reportedly "processes
commands, controls software, and interfaces with hardware systems like
web-shooter-style mechanisms," including posting videos to Instagram. No
concrete technique, architecture, code, or API was actually described — it's
a highlight reel with a caption, not a tutorial.

Rather than fabricate a fake "Jarvis" (there's nothing to copy — no code,
prompts, or wiring diagrams were shown), this repo implements a **reasonable,
standalone, legitimate version of what the caption is gesturing at**: a small
command-routing assistant that maps natural-language instructions to
pluggable "skills," including (1) publishing a video to Instagram and (2)
sending a trigger command to a locally-attached hardware gadget.

## What it does

`jarvis.py` is a tiny CLI assistant:

1. You give it a plain-English command, e.g.
   - `"post video https://cdn.example.com/clip.mp4 with caption 'launch day!'"`
   - `"fire the web shooter"`
2. It parses the command with a small rule-based matcher (`jarvis.py`) and
   routes it to a skill in `skills/`.
3. Each skill either performs the real action (if you've configured
   credentials/hardware) or safely simulates it (`--dry-run`, or
   automatically when config is missing).

Two skills are included:

- **`skills/instagram_post.py`** — publishes a video/Reel to an Instagram
  Business or Creator account using **Meta's official Instagram Graph API**
  (the same API legitimate scheduling tools like Buffer/Later use). It
  requires your own Facebook App + access token, obtained through Meta's
  normal developer OAuth flow. It does **not** log into Instagram's website,
  automate a browser, or touch any private/undocumented endpoint.

- **`skills/hardware_trigger.py`** — sends a short command over a local
  **serial (USB) connection** to a device you own (e.g. an Arduino/ESP32
  driving a servo or solenoid for a DIY "web shooter" rig). It only ever
  talks to a serial port on your machine — no networking, no reaching other
  people's devices.

## What it deliberately does NOT do

This build stays within the hard limits for this project: no bot/fraud
detection evasion, no credential harvesting, no scraping in violation of a
platform's terms of service. Concretely:

- Instagram publishing goes through the official Graph API with a token
  *you* generate and consent to via Meta's own OAuth screen — never a
  scraped session, cookie theft, or headless-browser login automation.
- The Graph API requires the video to already be hosted at a public HTTPS
  URL; this tool does not attempt to spin up hosting/tunnels for you, and
  it will clearly error out (not silently misbehave) if you pass a local
  file path instead of a URL.
- Hardware control is local-serial-only. There is no remote-control,
  device-hijacking, or "control someone else's hardware" capability.

## Setup

```bash
cd jarvis  # this directory
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Dependencies are optional at runtime — the tool auto-falls-back to
`--dry-run` behavior for any skill whose config/library isn't present, so
you can try it with zero setup:

```bash
python3 jarvis.py "post video https://example.com/clip.mp4 with caption 'hi'" --dry-run
python3 jarvis.py "fire the web shooter" --dry-run
python3 jarvis.py --interactive
```

### Enabling real Instagram posting

1. Create a Facebook App at https://developers.facebook.com/apps and add the
   "Instagram Graph API" product.
2. Link an Instagram **Business or Creator** account to a Facebook Page you
   admin, and connect that Page to the app.
3. Generate a long-lived access token with the `instagram_content_publish`
   permission (Meta's Graph API Explorer or the standard OAuth flow both
   work — follow Meta's official docs, since token generation flows change).
4. Find your Instagram Business Account's numeric ID (via
   `GET /me/accounts` → `instagram_business_account`).
5. Set environment variables:
   ```bash
   export IG_USER_ID="1234567890"
   export IG_ACCESS_TOKEN="EAAG..."
   # optional, defaults to v19.0
   export IG_GRAPH_API_VERSION="v19.0"
   ```
6. Host your video file at a public HTTPS URL (S3, R2, any CDN/web host —
   this tool does not host it for you), then:
   ```bash
   python3 jarvis.py "post video https://your-cdn.example.com/clip.mp4 with caption 'launch day!'"
   ```

Without `IG_USER_ID`/`IG_ACCESS_TOKEN` set, this skill always runs in dry-run
mode and just prints what it would have done.

### Enabling real hardware control

1. Flash your Arduino/ESP32 with a sketch that reads a line like
   `WEB_SHOOTER:FIRE\n` over serial and replies `OK\n` (or `ERR <reason>\n`).
   (Sketch not included — this is a protocol contract, not a wiring guide,
   since the reel didn't show one either.)
2. Find your serial port name:
   - macOS: `ls /dev/tty.usb*`
   - Windows: check Device Manager for the COM port
   - Linux: `ls /dev/ttyUSB*` or `/dev/ttyACM*`
3. Set environment variables:
   ```bash
   export JARVIS_SERIAL_PORT="/dev/tty.usbmodem14101"
   export JARVIS_SERIAL_BAUD="9600"   # optional, this is the default
   ```
4. Run:
   ```bash
   python3 jarvis.py "fire the web shooter"
   ```

Without `JARVIS_SERIAL_PORT` set, this skill always runs in dry-run mode.

## Files

- `jarvis.py` — CLI entry point, command parsing, skill dispatch.
- `skills/instagram_post.py` — Instagram Graph API publishing.
- `skills/hardware_trigger.py` — local serial hardware control.
- `requirements.txt` — optional dependencies (`requests`, `pyserial`).

## Extending it

Add a new skill by writing a function in `skills/`, adding a regex/pattern to
`parse_command()` in `jarvis.py`, and wiring it into `dispatch()`. The
matcher is intentionally simple (regex, not an LLM) so the whole thing runs
offline with no API key required just to explore the code — swap in an LLM
call there if you want fuzzier natural-language understanding.
