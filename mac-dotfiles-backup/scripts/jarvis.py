import os
import sys
import time
import errno
import subprocess
import json
import tempfile
import urllib.request

LOCK_PATH = "/tmp/jarvis.lock"
STALE_LOCK_SECONDS = 120  # a run should never take this long; treat older locks as dead


def acquire_lock():
    # Atomic create-or-fail so overlapping launches can't both proceed,
    # even if something ever calls jarvis.py back-to-back without a cooldown.
    try:
        fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        try:
            age = time.time() - os.path.getmtime(LOCK_PATH)
            if age > STALE_LOCK_SECONDS:
                os.remove(LOCK_PATH)
                return acquire_lock()
        except FileNotFoundError:
            return acquire_lock()
        return False


def release_lock():
    try:
        os.remove(LOCK_PATH)
    except FileNotFoundError:
        pass


def speak(text):
    # macOS built-in Text-to-Speech
    subprocess.run(["say", text])

def main():
    print("Jarvis activated.")
    speak("Yes sir. Listening.")

    # Use a private per-run temp dir so the wav/txt can't be pre-created,
    # symlinked, or left stale by another process/run sharing fixed /tmp paths.
    with tempfile.TemporaryDirectory(prefix="jarvis_cmd_") as tmpdir:
        wav_path = os.path.join(tmpdir, "jarvis_cmd.wav")
        txt_path = os.path.join(tmpdir, "jarvis_cmd.txt")

        # Record 4 seconds using ffmpeg on macOS (avfoundation)
        subprocess.run(
            [
                "/usr/local/Cellar/ffmpeg/8.0.1_4/bin/ffmpeg",
                "-y", "-f", "avfoundation", "-i", ":0", "-t", "4",
                wav_path, "-loglevel", "quiet",
            ]
        )
        speak("Processing.")

        # Transcribe locally with Whisper (running inside the safe venv)
        subprocess.run(
            [
                "/Users/natehoward/AgentDrop-Workspace/venv/bin/whisper",
                wav_path, "--model", "tiny", "--output_dir", tmpdir, "--output_format", "txt",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            with open(txt_path, "r") as f:
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
