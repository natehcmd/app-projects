# DZY4CWVPiXl — Clap-triggered workflow launcher

## Source content

> @hex.gar: Been messing with this little Python thing where a double clap
> kicks off my morning workflow. Honestly feels ridiculous in the best way.
> It's free, it's open source, steal it, break it, make it yours.
> Comment Jarvis if you want the PDF walkthrough.

No actual code or implementation detail was included in the source — the
"PDF walkthrough" was gated behind a comment funnel. The one concrete idea
present is the concept itself: **detect a double clap via microphone and use
it as a trigger to launch a script.**

## What was built

`clap_trigger.py` — a best-effort implementation of that concept:

- Opens the default microphone with `sounddevice`
- Computes RMS volume per audio block
- Flags a "clap" when RMS crosses a threshold, with a minimum gap so one
  loud sustained noise doesn't count as multiple claps
- If two claps land within `--clap-window` seconds of each other, runs the
  configured `--command` via `subprocess.Popen`
- Has a cooldown after triggering so the same double-clap doesn't fire twice

## Usage

```bash
pip install -r requirements.txt
python clap_trigger.py --command "python /Users/natehoward/Projects/mission-control/scripts/morning_brief.py"
```

Tune `--threshold` to your mic/room noise floor (start around 0.2-0.4 and
adjust based on false positives/negatives).

## Status

**built = true** — working best-effort implementation of the described
concept. Threshold values are reasonable defaults, not tuned against a real
mic, since no audio samples were available in the source material.
