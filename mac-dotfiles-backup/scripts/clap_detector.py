import os
import time
import fcntl
import subprocess
import numpy as np
import sounddevice as sd

THRESHOLD = 0.5  # Adjust sensitivity
CLAP_COOLDOWN = 0.2
DOUBLE_CLAP_WINDOW = 1.0
RETRIGGER_LOCKOUT = 30  # seconds to ignore claps after a trigger, so jarvis's own
                        # speaker output isn't picked up by the mic as a new clap

# Same lock file jarvis.py itself takes with fcntl.flock (see jarvis.py).
JARVIS_LOCK_PATH = "/tmp/jarvis.lock"

last_spike = 0
last_trigger = 0
clap_count = 0


def jarvis_already_running() -> bool:
    # `pgrep -f scripts/jarvis.py` matches ANY process whose command line
    # contains that substring — including e.g. `vim scripts/jarvis.py` or a
    # grep of this very file — which would wrongly report jarvis as "running"
    # and silently swallow a real double-clap trigger. Checking jarvis's own
    # flock is exact: it can only be held by a real, currently-running
    # jarvis.py process, and the kernel guarantees it's released the instant
    # that process exits or dies.
    try:
        fd = os.open(JARVIS_LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False  # we got the lock uncontended => jarvis is not running
    except OSError:
        return True  # lock is held by another process => jarvis is running
    finally:
        os.close(fd)


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


def main():
    # Run in background
    with sd.InputStream(callback=audio_callback):
        while True:
            time.sleep(1)


if __name__ == "__main__":
    # Guard the mic-listening loop so the module can be imported (e.g. to
    # unit-test jarvis_already_running()) without opening the microphone or
    # blocking forever.
    main()
