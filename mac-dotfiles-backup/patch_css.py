import sys
import re

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. Replace :root for agent tracker
    if 'agent-tracker' in filepath:
        new_root = """  :root {
    --bg: #0b0d12;
    --bg2: #11141c;
    --ink: #e8eaf2;
    --ink-dim: #9aa0b4;
    --ink-faint: #7b829b;
    --mint: #9fe8c9;
    --lav: #c3b8f5;
    --peach: #f5c9a8;
    --rose: #f2a9c4;
    --sky: #a8d8f5;
    --glass: rgba(255, 255, 255, 0.045);
    --glass-brd: rgba(255, 255, 255, 0.09);
    --r: 18px; /* Border radius */
    --shadow: 0 8px 32px rgba(0, 0, 0, 0.35);

    --bg-deep: var(--bg2);
    --panel: var(--glass);
    --panel-solid: var(--bg2);
    --panel-2: rgba(255, 255, 255, 0.08);
    --line: var(--glass-brd);
    --ink-mid: var(--ink-dim);
    --accent: var(--mint);
    --accent-ink: #0b2018;
    --danger: var(--rose);
    --ok: var(--mint);
    --warn: var(--peach);
    --radius: var(--r);
    --z-panel: 10;
    --z-toast: 40;
    --z-modal: 50;
    --ease: cubic-bezier(0.22, 1, 0.36, 1);
    font-size: 15px;
  }"""
        content = re.sub(r'  :root\s*\{.*?\sfont-size: 15px;\n  \}', new_root, content, flags=re.DOTALL)
        
        # Body background
        new_body = """  body {
    font-family: "Avenir Next", -apple-system, "SF Pro Text", Inter, system-ui, sans-serif;
    background:
      radial-gradient(1200px 800px at 70% -10%, rgba(195, 184, 245, 0.15), transparent 60%),
      radial-gradient(900px 700px at 10% 110%, rgba(159, 232, 201, 0.15), transparent 55%),
      var(--bg);
    color: var(--ink);
    overflow: hidden;
  }"""
        content = re.sub(r'  body\s*\{.*?overflow: hidden;\n  \}', new_body, content, flags=re.DOTALL)

        # .topbar
        content = re.sub(
            r'    background: oklch\(0\.19 0\.02 255 / 0\.85\);\n    backdrop-filter: blur\(14px\);\n    border-bottom: 1px solid var\(--line\);',
            r'    background: var(--glass);\n    backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);\n    border-bottom: 1px solid var(--glass-brd);',
            content
        )

        # .sidebar
        content = re.sub(
            r'    border-right: 1px solid var\(--line\);\n    background: oklch\(0\.19 0\.02 255 / 0\.6\);\n    backdrop-filter: blur\(10px\);',
            r'    border-right: 1px solid var(--glass-brd);\n    background: var(--glass);\n    backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);',
            content
        )

        # .btn
        content = re.sub(
            r'    padding: 6px 12px; border-radius: 9px;\n    border: 1px solid var\(--line\);\n    background: oklch\(0\.26 0\.022 255 / 0\.6\);',
            r'    padding: 6px 12px; border-radius: var(--r);\n    border: 1px solid var(--glass-brd);\n    background: var(--glass);',
            content
        )
        content = re.sub(
            r'  \.btn\.primary \{\n    background: var\(--accent\); color: var\(--accent-ink\);\n    border-color: transparent; font-weight: 600;\n  \}\n  \.btn\.primary:hover \{ background: oklch\(0\.87 0\.09 230\); color: var\(--accent-ink\); \}',
            r'  .btn.primary {\n    background: linear-gradient(135deg, var(--mint), #6fd3a8); color: #0b2018;\n    border-color: transparent; font-weight: 600;\n  }\n  .btn.primary:hover { background: linear-gradient(135deg, #6fd3a8, #5bbf96); color: #0b2018; }',
            content
        )

        # .detail
        content = re.sub(
            r'    background: var\(--panel\); backdrop-filter: blur\(16px\);\n    border: 1px solid var\(--line\); border-radius: var\(--radius\);\n    padding: 16px; z-index: var\(--z-panel\);\n',
            r'    background: var(--glass); backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);\n    border: 1px solid var(--glass-brd); border-radius: var(--r);\n    box-shadow: var(--shadow);\n    padding: 16px; z-index: var(--z-panel);\n',
            content
        )

        # .chat-panel
        content = re.sub(
            r'    background: oklch\(0\.16 0\.017 255 / 0\.94\);\n    backdrop-filter: blur\(14px\);\n    border: 1\.5px solid var\(--line\);\n    border-radius: 12px;\n    overflow: hidden;\n    box-shadow: 0 14px 36px oklch\(0 0 0 / 0\.45\);',
            r'    background: var(--glass);\n    backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);\n    border: 1px solid var(--glass-brd);\n    border-radius: var(--r);\n    overflow: hidden;\n    box-shadow: var(--shadow);',
            content
        )

        # hint kbd
        content = re.sub(
            r'    font-family: ui-monospace, SF Mono, monospace; font-size: 0\.72rem;',
            r'    font-family: "SF Mono", Menlo, monospace; font-size: 0.72rem;',
            content
        )

    # 2. Replace for file graph
    if 'file-graph' in filepath:
        new_root = """  :root {
    --bg: #0b0d12;
    --bg2: #11141c;
    --ink: #e8eaf2;
    --ink-dim: #9aa0b4;
    --ink-faint: #7b829b;
    --mint: #9fe8c9;
    --lav: #c3b8f5;
    --peach: #f5c9a8;
    --rose: #f2a9c4;
    --sky: #a8d8f5;
    --glass: rgba(255, 255, 255, 0.045);
    --glass-brd: rgba(255, 255, 255, 0.09);
    --r: 18px; /* Border radius */
    --shadow: 0 8px 32px rgba(0, 0, 0, 0.35);

    --panel: var(--glass); --border: var(--glass-brd);
    --text: var(--ink); --dim: var(--ink-dim);
    --accent: var(--mint); --green: var(--mint); --pink: var(--rose); --amber: var(--peach);
    --red: var(--rose); --cyan: var(--sky);
  }"""
        content = re.sub(r'  :root\s*\{.*?\n  \}', new_root, content, count=1, flags=re.DOTALL)

        new_body = r'  body { background: radial-gradient(circle at 15% 50%, rgba(195, 184, 245, 0.15), transparent 25%), radial-gradient(circle at 85% 30%, rgba(159, 232, 201, 0.15), transparent 25%), radial-gradient(circle at 50% 80%, rgba(242, 169, 196, 0.15), transparent 25%), var(--bg); color: var(--text); font: 14px/1.5 "Avenir Next", -apple-system, "SF Pro Text", sans-serif; overflow: hidden; height: 100vh; }'
        content = re.sub(r'  body\s*\{.*?height: 100vh; \}', new_body, content, count=1, flags=re.DOTALL)
        
        # Panel
        content = re.sub(
            r'  \.panel \{ position: fixed; background: var\(--panel\); backdrop-filter: blur\(18px\); -webkit-backdrop-filter: blur\(18px\); border: 1px solid var\(--border\); border-radius: 16px; padding: 14px; box-shadow: 0 8px 32px rgba\(0,0,0,\.4\); \}',
            r'  .panel { position: fixed; background: var(--glass); backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px); border: 1px solid var(--glass-brd); border-radius: var(--r); padding: 14px; box-shadow: var(--shadow); }',
            content
        )

        # Buttons
        content = re.sub(
            r'  select, button \{ background: rgba\(255,255,255,\.06\); border: 1px solid var\(--border\); border-radius: 10px; color: var\(--text\); padding: 8px 12px; font-size: 13px; cursor: pointer; \}',
            r'  select, button { background: var(--glass); border: 1px solid var(--border); border-radius: var(--r); color: var(--text); padding: 8px 12px; font-size: 13px; cursor: pointer; transition: 0.2s; }',
            content
        )

    with open(filepath, 'w') as f:
        f.write(content)

for p in sys.argv[1:]:
    process_file(p)
