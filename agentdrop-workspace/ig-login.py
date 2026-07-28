#!/usr/bin/env python3
"""One-time CLI login for the AgentDrop curation account — no browser needed.

Run this interactively in Terminal:

  ~/AgentDrop-Workspace/.venv/bin/python ~/AgentDrop-Workspace/ig-login.py

It prompts for the username and password (password is hidden while typing,
never stored), handles a verification-code challenge if Instagram sends one,
and saves the resulting session to .ig-session.json. From then on the
curation pipeline (ig-curate.py / ig-fetch.py) uses this session and ignores
browsers entirely. Re-run this script any time to switch accounts.

If Instagram raises its "native challenge" checkpoint: approve the login
attempt in the Instagram app (or instagram.com) — look for the "Was this
you?" / suspicious-login prompt — then re-run this script. Device identifiers
are persisted in .ig-device.json across attempts so the retry looks like the
same device, which is what makes Instagram accept it.
"""
import getpass
import os
import sys

from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired

WORKSPACE = os.path.expanduser("~/AgentDrop-Workspace")
SESSION_PATH = os.path.join(WORKSPACE, ".ig-session.json")
DEVICE_PATH = os.path.join(WORKSPACE, ".ig-device.json")


def code_handler(username, choice):
    return input(f"Verification code Instagram sent to your {choice}: ").strip()


def main():
    username = input("Instagram username: ").strip().lstrip("@")
    password = getpass.getpass("Password (hidden while typing): ")

    cl = Client()
    cl.delay_range = [1, 3]
    cl.challenge_code_handler = code_handler
    # Reuse device identifiers from a previous attempt — after approving a
    # checkpoint in the IG app, the retry must look like the SAME device.
    if os.path.exists(DEVICE_PATH):
        try:
            cl.load_settings(DEVICE_PATH)
            print("(reusing device identity from the previous attempt)")
        except Exception:
            pass

    try:
        cl.login(username, password)
    except ChallengeRequired:
        cl.dump_settings(DEVICE_PATH)
        os.chmod(DEVICE_PATH, 0o600)
        print()
        print("⚠️  Instagram wants you to approve this login on a trusted device:")
        print("   1. Open the Instagram app on your phone (or instagram.com)")
        print("      logged in as @" + username)
        print("   2. Look for the 'Was this you?' / suspicious-login prompt")
        print("      (also check the heart/notifications tab and your email)")
        print("      and approve it / confirm it was you.")
        print("   3. Re-run this script — it will reuse the same device identity,")
        print("      which is what makes Instagram accept the retry.")
        sys.exit(1)

    cl.dump_settings(SESSION_PATH)
    os.chmod(SESSION_PATH, 0o600)
    if os.path.exists(DEVICE_PATH):
        os.remove(DEVICE_PATH)
    print(f"✅ Logged in as @{cl.username} — session saved to {SESSION_PATH}")
    print("The curator uses this session from now on; no browser login needed.")


if __name__ == "__main__":
    main()
