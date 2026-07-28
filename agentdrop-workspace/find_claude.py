import sqlite3
import os

DB_PATH = os.path.expanduser("~/Projects/mission-control/data/mission.db")

def find_claude_tips():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get all transcripts
    c.execute("SELECT id, transcript FROM reels WHERE transcript != ''")
    all_reels = c.fetchall()
    conn.close()
    
    print("Mentions of Claude in reels:")
    for rid, tx in all_reels:
        if "claude" in tx.lower() or "clawed" in tx.lower() or "cloud code" in tx.lower():
            # Print sentences containing the keyword
            sentences = tx.split('.')
            for s in sentences:
                s_lower = s.lower()
                if "claude" in s_lower or "clawed" in s_lower or "cloud code" in s_lower:
                    print(f"- {s.strip()}")

if __name__ == "__main__":
    find_claude_tips()
