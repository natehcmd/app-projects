import os
import sqlite3
import glob

DB_PATH = os.path.expanduser("~/Projects/mission-control/data/mission.db")

def update_and_dedupe():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. First, let's make sure ALL 141 reels are in the DB.
    # The original seed_reels might have missed some transcripts.
    
    # Grab all transcripts from the agent results
    subagent_tx = glob.glob(os.path.expanduser("~/AgentDrop-Workspace/results_*/transcripts/*.txt"))
    for file_path in subagent_tx:
        rid = os.path.basename(file_path).replace(".txt", "")
        with open(file_path, "r", encoding="utf-8") as f:
            transcript = f.read().strip()
            
        # Update DB with this transcript if it's empty
        c.execute("UPDATE reels SET transcript = ? WHERE id = ? AND (transcript IS NULL OR transcript = '')", (transcript, rid))
        
        c.execute("INSERT OR IGNORE INTO reels (id, url, transcript) VALUES (?, ?, ?)", 
                  (rid, f"https://instagram.com/reel/{rid}", transcript))
                  
    conn.commit()
    print("Updated database with subagent transcripts.")
    
    # 2. Find and remove duplicates based on transcript
    c.execute("SELECT id, transcript FROM reels WHERE transcript != ''")
    all_reels = c.fetchall()
    
    seen_transcripts = {}
    duplicates_to_delete = []
    
    for rid, transcript in all_reels:
        # Normalize transcript for comparison (lowercase, remove spaces/punctuation)
        normalized = "".join(filter(str.isalnum, transcript.lower()))
        
        if not normalized:
            continue
            
        if normalized in seen_transcripts:
            duplicates_to_delete.append(rid)
        else:
            seen_transcripts[normalized] = rid
            
    print(f"Found {len(duplicates_to_delete)} duplicate reels.")
    
    for rid in duplicates_to_delete:
        # Delete from DB
        c.execute("DELETE FROM reels WHERE id = ?", (rid,))
        
    conn.commit()
    conn.close()
    
    print(f"Deleted {len(duplicates_to_delete)} duplicate reels from Mission Control database.")
    print(f"Total unique reels remaining in database: {len(seen_transcripts)}")

if __name__ == "__main__":
    update_and_dedupe()
