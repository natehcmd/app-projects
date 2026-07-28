# Claude Reels: Local Workflows & Custom Implementations

This document acts as an interactive index of the workflows and tools you saved in your Reels archive. It explains **how they work**, **how to build them locally**, and **how to configure them securely** so that you (or any AI agent reviewing your workspace) can quickly adapt them.

---

## 1. Graphify (Codebase Dependency Mapping)
* **Reel IDs:** `DXAshxEDM5m`, `DZWLmJQuw-7`, `Dae5fOUOphe`
* **Core Idea:** Avoid token re-reads by parsing your codebase structure once into a lightweight map, instead of having Claude read all source files at the start of every session.

### How it Works
1. A local scanner builds a text-based graph of directories, files, and core programming symbols (class definitions, function headers, exports).
2. The scanner outputs a single file (e.g., `.repomap.txt`).
3. Claude reads only this map to understand file coordinates, then only loads the actual contents of the target files it needs to modify.

### How to Make It
Write a recursive script that ignores binary files and caches, extracts symbols using regex, and formats it as a hierarchical tree.
*   **Secure Implementation:** Run `python3 ~/scripts/repomap.py . > .repomap.txt` before starting an agent session. Use the Python script defined in [safe_workflow_adoption.md](file:///Users/natehoward/.gemini/antigravity-cli/brain/6a8a709c-39f5-4266-8619-2cb1c784bb12/safe_workflow_adoption.md) for zero dependencies.

---

## 2. Understand-Anything (Interactive Codebase Graph)
* **Reel ID:** `DadvdvitVke`
* **Core Idea:** Convert a large codebase into an interactive knowledge base with visual file relationships.

### How it Works
1. Statically analyzes imports and require statements across code files.
2. Generates an adjacency matrix (e.g., `app.js` imports `auth.js`).
3. Renders a local, interactive web page with a force-directed SVG node graph (using D3.js).

### How to Make It
1. Use your existing **`file-graph`** project! It already stores files in `~/.filegraph/filegraph.db`.
2. Expand the frontend of your merged `mission-control` dashboard (Port `8450`) to request file relations from the FileGraph DB and render them in a force-directed HTML5 canvas.
3. Expose a `/settings` tool inside your MCP server so you can click any node to pull up the associated file preview.

---

## 3. Jarvis Voice Dashboard / Hermes Agent Harness
* **Reel IDs:** `DZc0F3Nx2rb`, `DZ5H6F1Rz1S`, `DaC9aW6Miyi`, `DaebyH0xIDQ`
* **Core Idea:** A voice-activated workspace assistant that handles system stats, updates daily briefs, and runs browser automations.

### How it Works
1. Runs an audio capture loop (via a menu-bar widget or background daemon).
2. Uses local wake-phrase detection ("Hey Jarvis") and amplitude-spike analysis (double-clap detection).
3. Transcribes commands locally, passes them to a background FastAPI agent router, and speaks back using a Text-to-Speech API.

### How to Make It
1. **Wake Loop & Clap Detector:** Run a local Python script utilizing the `sounddevice` package (see the clap detector script in [safe_workflow_adoption.md](file:///Users/natehoward/.gemini/antigravity-cli/brain/6a8a709c-39f5-4266-8619-2cb1c784bb12/safe_workflow_adoption.md)).
2. **Audio Actions:** Configure the Python script to trigger your custom shell modes:
   ```bash
   bash ~/.modes/mode.sh morning
   ```
3. **Voice Outputs:** Wrap your FastAPI server response in macOS's built-in `say` terminal command:
   ```bash
   say "Good morning. Briefing is ready."
   ```

---

## 4. ECC (Everything Claude Code / 119 Skills)
* **Reel IDs:** `DZCzO6GE0y7`, `DZpySOnOCxI`
* **Core Idea:** A repository aggregating pre-configured subagents, terminal hooks, and skills.

### How it Works
Instead of installing a single giant package, split capabilities into modular, single-responsibility files that can be loaded dynamically based on project files.

### How to Make It
Set up a structured `skills` folder inside your centralized projects. For each skill, include:
*   A `SKILL.md` file describing what the skill does and what commands to run.
*   A corresponding scripts directory containing the executables.
*   Your main agent framework should scan `~/Projects/apps-and-skills` and register them as prompt configurations dynamically.

---

## 5. Front-End Design & Visual QC Skills
* **Reel IDs:** `DafiQ5iPlC7`, `DZow139P5Wd`
* **Core Idea:** Equipping text-based agents with visual capabilities to prevent ugly CSS design.

### How it Works
1. **Design Extraction (`Skill UI`):** Download website assets or styles, parsing classes into a design guidelines markdown document.
2. **Design Quality Control (`Playwright CLI`):** Once code is written, the agent launches a browser, captures a page screenshot, and reviews it using a vision-enabled model to auto-fix layout bugs.

### How to Make It
1. Write a script `~/scripts/screenshot-preview.js` using **Playwright** or **Puppeteer** (Node.js).
2. Expose it to your agent as a tool. When editing styles, instruct the agent to run:
   ```bash
   node ~/scripts/screenshot-preview.js http://localhost:3000 build/preview.png
   ```
3. The agent then reads the file `build/preview.png` using its binary viewing tools to visually inspect the UI and fix layout anomalies before completing the task.
