#!/usr/bin/env python3
"""Clap-triggered workflow launcher.

Listens to the default microphone and watches for a double-clap
(two sharp volume spikes within a short window). On detection, runs
a configured shell command (e.g. a morning routine script).

Inspired by an AgentDrop reel (@hex.gar) describing a "double clap
kicks off my morning workflow" Python trigger. No implementation
details were given in the source, so this is a best-effort build of
the concept: real-time audio energy spike detection -> subprocess call.

Usage:
    pip install -r requirements.txt
    python clap_trigger.py --command "python morning_brief.py"
"""
import argparse
import subprocess
import time
from collections import deque

import numpy as np
import sounddevice as sd


def main():
    parser = argparse.ArgumentParser(description="Run a command when you double-clap.")
    parser.add_argument("--command", help="Shell command to run on trigger (required unless --calibrate)")
    parser.add_argument("--threshold", type=float, default=0.3, help="Volume spike threshold (0-1 RMS)")
    parser.add_argument("--clap-window", type=float, default=1.2, help="Max seconds between the two claps")
    parser.add_argument("--cooldown", type=float, default=5.0, help="Seconds to ignore audio after a trigger")
    parser.add_argument("--samplerate", type=int, default=16000)
    parser.add_argument("--blocksize", type=int, default=1024)
    parser.add_argument("--calibrate", action="store_true",
                         help="Print live RMS levels instead of triggering — tap the case and watch the numbers.")
    args = parser.parse_args()
    if not args.calibrate and not args.command:
        parser.error("--command is required unless --calibrate is set")

    if args.calibrate:
        def show_level(indata, frames, time_info, status):
            rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
            bar = "#" * min(int(rms * 200), 60)
            print(f"\rRMS: {rms:.4f} {bar}" + " " * 20, end="", flush=True)
        print("[calibrate] tap the case a few times, watch the peak RMS values. Ctrl+C to stop.")
        with sd.InputStream(channels=1, samplerate=args.samplerate,
                             blocksize=args.blocksize, dtype="int16", callback=show_level):
            while True:
                time.sleep(0.1)

    clap_times = deque(maxlen=2)
    last_trigger = 0.0
    last_clap = 0.0
    min_gap = 0.15  # ignore sustained loud noise as one long "clap"

    def audio_callback(indata, frames, time_info, status):
        nonlocal last_trigger, last_clap
        now = time.time()
        if now - last_trigger < args.cooldown:
            return

        rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
        if rms < args.threshold:
            return
        if now - last_clap < min_gap:
            return

        last_clap = now
        clap_times.append(now)

        if len(clap_times) == 2 and (clap_times[1] - clap_times[0]) <= args.clap_window:
            print(f"[clap_trigger] double clap detected, running: {args.command}")
            subprocess.Popen(args.command, shell=True)
            last_trigger = now
            clap_times.clear()

    print(f"[clap_trigger] listening... threshold={args.threshold} window={args.clap_window}s")
    with sd.InputStream(
        channels=1,
        samplerate=args.samplerate,
        blocksize=args.blocksize,
        dtype="int16",
        callback=audio_callback,
    ):
        while True:
            time.sleep(0.1)


if __name__ == "__main__":
    main()
