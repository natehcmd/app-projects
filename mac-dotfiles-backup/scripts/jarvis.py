import os
import sys
import time
import errno
import fcntl
import subprocess
import json
import urllib.request

LOCK_PATH = "/tmp/jarvis.lock"

# Module-level fd for the held lock, so release_lock() can unlock/close the
# exact descriptor that holds it.
_lock_fd = None


def acquire_lock():
    # fcntl.flock is kernel-enforced and tied to this process: if the holder
    # dies for any reason (crash, kill -9, power loss), the kernel releases
    # the lock automatically when the fd's last reference closes — no mtime
    # "staleness" heuristic needed. The old remove-if-stale-then-recreate
    # approach let a second process decide a still-running-but-slow jarvis
    # was dead (if a run legitimately took longer than the stale threshold)
    # and rip its lock out from under it, so both ran at once.
    global _lock_fd
    fd = os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return False
    os.ftruncate(fd, 0)
    os.write(fd, str(os.getpid()).encode())
    _lock_fd = fd
    return True


def release_lock():
    global _lock_fd
    if _lock_fd is None:
        return
    try:
        fcntl.flock(_lock_fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(_lock_fd)
    except OSError:
        pass
    _lock_fd = None


def speak(text):
    # macOS built-in Text-to-Speech
    subprocess.run(["say", text])

def main():
    print("Jarvis activated.")
    speak("Yes sir. Listening.")

    # Record 4 seconds using ffmpeg on macOS (avfoundation)
    os.system("/usr/local/Cellar/ffmpeg/8.0.1_4/bin/ffmpeg -y -f avfoundation -i ':0' -t 4 /tmp/jarvis_cmd.wav -loglevel quiet")
    speak("Processing.")

    # Transcribe locally with Whisper (running inside the safe venv)
    os.system("/Users/natehoward/AgentDrop-Workspace/venv/bin/whisper /tmp/jarvis_cmd.wav --model tiny --output_dir /tmp --output_format txt > /dev/null 2>&1")

    try:
        with open("/tmp/jarvis_cmd.txt", "r") as f:
            cmd = f.read().strip()
    except Exception:
        cmd = ""

    print(f"Heard: {cmd}")

    if not cmd or len(cmd) < 2:
        speak("I didn't catch that.")
        return

    # Pass the local transcription to the Mission Control FastAPI agent router
    data = json.dumps({
        "messages": [{"role": "user", "content": cmd}],
        "engine": "local"
    }).encode('utf-8')

    req = urllib.request.Request("http://localhost:8450/api/chat", data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            res = json.loads(response.read())
            msg = res.get("message", "No response.")
            # Remove characters that might mess up the 'say' command
            clean_msg = msg.replace('"', '').replace("'", "")
            print(f"Agent response: {clean_msg}")
            speak(clean_msg)
    except Exception as e:
        speak("Sorry, I could not reach the agent router.")

if __name__ == "__main__":
    if not acquire_lock():
        print("Jarvis is already running, skipping this trigger.")
        sys.exit(0)
    try:
        main()
    finally:
        release_lock()
