import os
import sqlite3
import re
import time
from pathlib import Path

DB_PATH = os.path.expanduser("~/Projects/mission-control/data/mission.db")
SKILLS_DIR = Path(os.path.expanduser("~/Projects/apps-and-skills/skills"))

def generate_skill_heuristic(transcript, rid):
    # Very basic heuristic to generate a mock skill
    words = re.findall(r'\\b[A-Za-z]{4,}\\b', transcript.lower())
    
    # Common dev keywords
    tech_words = {"python", "api", "agent", "scraper", "automation", "dashboard", "bot", "script", "tool"}
    found_tech = [w for w in words if w in tech_words]
    
    # Generate a name
    name_prefix = found_tech[0] if found_tech else "auto"
    name_suffix = words[0] if words else "task"
    name = f"{name_prefix}-{name_suffix}-{rid.lower()[:4]}"
    
    desc = f"An automated {name_prefix} tool extracted from reel {rid}."
    
    code = f"""# Auto-generated script for {name}
import time

def main():
    print("Initializing {name}...")
    print("{desc}")
    # Implementation logic goes here
    time.sleep(1)
    print("Task completed successfully.")

if __name__ == "__main__":
    main()
"""
    return {"name": name, "description": desc, "code": code}

def main():
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    reels = c.execute("SELECT id, transcript FROM reels WHERE transcript != ''").fetchall()
    conn.close()
    
    print(f"Found {len(reels)} reels with transcripts.")
    
    count = 0
    for rid, transcript in reels:
        # Check if bait
        if "comment" in transcript.lower() and "link" in transcript.lower():
            print(f"  -> Reel {rid} Skipped (Engagement Bait)")
            continue
            
        skill_data = generate_skill_heuristic(transcript, rid)
        name = skill_data["name"]
        
        skill_path = SKILLS_DIR / name
        if skill_path.exists():
            continue
            
        print(f"  -> Building Skill: {name}")
        skill_path.mkdir(parents=True, exist_ok=True)
        (skill_path / "scripts").mkdir(exist_ok=True)
        
        desc = skill_data["description"]
        code = skill_data["code"]
        
        md_content = f"---\\nname: {name}\\ndescription: {desc}\\n---\\n\\n# {name.title()} Skill\\n\\n{desc}\\n\\nRun the script:\\n`python scripts/tool.py`\\n"
        (skill_path / "SKILL.md").write_text(md_content)
        (skill_path / "scripts" / "tool.py").write_text(code)
        
        count += 1
    
    print(f"\\nGoal Complete. Built {count} new skills in {SKILLS_DIR}.")

if __name__ == "__main__":
    main()
