import os
import re
import sys

DANGEROUS_PATTERNS = [
    r'os\.system\(.*curl.*\|.*bash',
    r'rm\s+-rf',
    r'subprocess\.Popen\(.*shell=True',
    r'eval\(',
    r'exec\('
]

def audit_skill_script(filepath):
    print(f"Auditing {filepath} for safety...")
    dangerous_findings = []
    
    if not os.path.exists(filepath):
        print("File not found.")
        return
        
    with open(filepath, 'r') as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, line):
                dangerous_findings.append((i+1, line.strip(), pattern))
                
    if dangerous_findings:
        print("WARNING: Sketchy code detected!")
        for line_num, code, pattern in dangerous_findings:
            print(f"Line {line_num}: {code} (Matched pattern: {pattern})")
    else:
        print("Script looks safe based on basic static analysis.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        audit_skill_script(sys.argv[1])
    else:
        print("Usage: python safe_claude_skill_auditor.py <script_to_audit.py>")
