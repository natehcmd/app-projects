import sys
import re

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # file-graph .badge
    if 'file-graph' in filepath:
        content = re.sub(
            r'\.badge \{ font-size: 10px; padding: 1px 6px; border-radius: 6px; background: rgba\(252,165,165,\.15\); color: var\(--red\); \}',
            r'.badge { font-size: 10px; padding: 1px 6px; border-radius: 999px; background: var(--glass); border: 1px solid var(--glass-brd); color: var(--rose); }',
            content
        )

    # agent-tracker .fleet-chip
    if 'agent-tracker' in filepath:
        content = re.sub(
            r'border: 1px solid var\(--line\); background: none;',
            r'border: 1px solid var(--line); background: var(--glass);',
            content
        )
        content = re.sub(
            r'  \.viewseg button \{ background: none;',
            r'  .viewseg button { background: var(--glass);',
            content
        )

    with open(filepath, 'w') as f:
        f.write(content)

for p in sys.argv[1:]:
    process_file(p)
