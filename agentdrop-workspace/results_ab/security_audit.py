import os
import re
import sys

def scan_directory(path):
    print(f"Starting security scan on {path}...")
    issues_found = 0
    
    # Simple regex for finding potential hardcoded passwords or secrets
    secret_patterns = [
        re.compile(r'(?i)password\s*=\s*[\'"][^\'"]+[\'"]'),
        re.compile(r'(?i)api[_-]?key\s*=\s*[\'"][^\'"]+[\'"]'),
        re.compile(r'(?i)secret\s*=\s*[\'"][^\'"]+[\'"]')
    ]
    
    for root, dirs, files in os.walk(path):
        # Skip hidden directories like .git
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            if file.endswith(('.py', '.js', '.ts', '.html', '.md')):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines):
                            for pattern in secret_patterns:
                                if pattern.search(line):
                                    print(f"[WARNING] Potential hardcoded secret found in {filepath} at line {i+1}")
                                    issues_found += 1
                except Exception as e:
                    pass
                    
    print(f"\nScan complete. Found {issues_found} potential security issues.")
    if issues_found > 0:
        print("Recommendation: Move sensitive data to environment variables and implement rate limiting on endpoints.")

if __name__ == "__main__":
    scan_path = sys.argv[1] if len(sys.argv) > 1 else "."
    scan_directory(scan_path)
