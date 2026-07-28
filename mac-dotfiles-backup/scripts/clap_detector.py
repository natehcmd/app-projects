import time
import subprocess
import numpy as np
import sounddevice as sd

THRESHOLD = 0.5  # Adjust sensitivity
CLAP_COOLDOWN = 0.2
DOUBLE_CLAP_WINDOW = 1.0
RETRIGGER_LOCKOUT = 30  # seconds to ignore claps after a trigger, so jarvis's own
                        # speaker output isn't picked up by the mic as a new clap

last_spike = 0
last_trigger = 0
clap_count = 0


def jarvis_already_running() -> bool:
    result = subprocess.run(["pgrep", "-f", "scripts/jarvis.py"], capture_output=True)
    return result.returncode == 0


def audio_callback(indata, frames, time_info, status):
    global last_spike, clap_count, last_trigger
    now = time.time()

    if now - last_trigger < RETRIGGER_LOCKOUT:
        return

    volume_norm = np.linalg.norm(indata) * 10

    if volume_norm > THRESHOLD:
        if now - last_spike > CLAP_COOLDOWN:
            if now - last_spike < DOUBLE_CLAP_WINDOW:
                clap_count += 1
            else:
                clap_count = 1

            last_spike = now
            print(f"Clap detected! (Count: {clap_count})")

            if clap_count == 2:
                clap_count = 0
                if jarvis_already_running():
                    print("Jarvis already running, ignoring double-clap.")
                    return
                print("Double-clap triggered! Spawning morning brief...")
                last_trigger = now
                # Run the Jarvis voice pipeline
                subprocess.Popen(["/opt/homebrew/bin/python3", "/Users/natehoward/scripts/jarvis.py"])


# Run in background
with sd.InputStream(callback=audio_callback):
    while True:
        time.sleep(1)
