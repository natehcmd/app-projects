import os
import glob

def scan_skills(skills_dir):
    print("Scanning for ECC agent skills...")
    skill_files = glob.glob(os.path.join(skills_dir, "**", "SKILL.md"), recursive=True)
    
    if not skill_files:
        print("No skills found.")
        return
        
    compiled_prompt = "You have access to the following specialized local skills:\n\n"
    
    for f in skill_files:
        with open(f, 'r') as file:
            content = file.read()
            compiled_prompt += f"--- Skill: {os.path.basename(os.path.dirname(f))} ---\n"
            compiled_prompt += content.strip() + "\n\n"
            
    print("\n--- GENERATED SYSTEM PROMPT FOR AGENT ---\n")
    print(compiled_prompt)

if __name__ == "__main__":
    skills_path = os.path.expanduser("~/Projects/apps-and-skills/skills")
    scan_skills(skills_path)
