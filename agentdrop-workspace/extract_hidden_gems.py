import os
import sqlite3
import glob
from pathlib import Path

DB_PATH = os.path.expanduser("~/Projects/mission-control/data/mission.db")
GEMS_FILE = Path(os.path.expanduser("~/Learning/hidden_gems_report.md"))

def extract_gems(transcript):
    # Look for capitalized words that might be tools or repos
    # Also look for basic tech terms
    tech_keywords = ["github", "repo", "python", "javascript", "react", "node", "api", "framework", "course", "tutorial", "learn"]
    
    gems = []
    
    # Extract any sentence containing a tech keyword
    sentences = transcript.split('.')
    for s in sentences:
        s_lower = s.lower()
        if any(k in s_lower for k in tech_keywords):
            if len(s.strip()) > 10:
                gems.append(s.strip())
                
    return gems

def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get DB transcripts
    db_reels = c.execute("SELECT id, transcript FROM reels WHERE transcript != ''").fetchall()
    conn.close()
    
    # Get File transcripts
    pattern = os.path.expanduser("~/AgentDrop-Workspace/results_*/transcripts/*.txt")
    transcript_files = glob.glob(pattern)
    
    file_reels = []
    for file_path in transcript_files:
        rid = os.path.basename(file_path).replace(".txt", "")
        with open(file_path, "r", encoding="utf-8") as f:
            file_reels.append((rid, f.read()))
            
    all_reels = db_reels + file_reels
    
    skipped_reels = []
    for rid, transcript in all_reels:
        if "comment" in transcript.lower() and "link" in transcript.lower():
            skipped_reels.append((rid, transcript))
            
    print(f"Found {len(skipped_reels)} skipped reels. Extracting gems...")
    
    report = "# Hidden Gems Extracted from Engagement-Bait Reels\\n\\n"
    report += "Even though these videos were 'comment-for-link' bait, here are the actual technical resources they mentioned:\\n\\n"
    
    extracted_count = 0
    for rid, transcript in skipped_reels:
        gems = extract_gems(transcript)
        if gems:
            report += f"### Reel {rid}\\n"
            for gem in set(gems): # Deduplicate sentences
                report += f"- {gem}\\n"
            report += "\\n"
            extracted_count += 1
            
    GEMS_FILE.write_text(report)
    print(f"Extraction complete! Found useful resources in {extracted_count} of the skipped reels.")
    print(f"Saved to {GEMS_FILE}")

if __name__ == "__main__":
    main()
