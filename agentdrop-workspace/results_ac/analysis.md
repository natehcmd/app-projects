# Reels Analysis Report

We analyzed a batch of 26 reels focusing on AI tools, development workflows, and productivity hacks. Here is a breakdown of the key concepts and tools extracted from the transcripts:

## 1. Agentic Frameworks and Routing
- **Rooflo / Ruflow**: An agentic framework that spins up to 60+ agents working in parallel. It features a router that sends simple tasks to cheaper models and complex tasks to more powerful ones, saving up to 75% on API costs. 
- **Hermes Agent (Jarvis)**: A local setup running on a Mac Mini, utilizing Hermes as an agentic harness. It coordinates multiple sub-agents (CEO, CMO, etc.) connected to tools like Slack, Telegram, and 11 Labs for voice.

## 2. Document Processing
- **MarkItDown**: A free tool by Microsoft that converts PDFs, Word docs, Excel sheets, and even YouTube videos into clean Markdown. This dramatically reduces token consumption (up to 70%) when passing documents to LLMs like Claude.

## 3. Local AI and Coding
- **Claude Code via Ollama**: A reel highlighted running coding agents completely locally and for free by using open-source models via Ollama, avoiding API costs entirely.
- **Custom Slash Commands**: A variety of custom commands (e.g., `/UI UX Pro Max`, `/front end design`, `/brave search`, `/fire crawl`) were discussed to trigger specific sub-agent behaviors and skills.

## 4. Career and Learning
- **Resume Optimization**: A specific prompt chain for using AI to rewrite resumes based on a job description, bypassing ATS filters, and using the Google XYZ formula (Accomplished X, measured by Y, by doing Z).
- **Python in 30 Days**: A learning path starting with Harvard CS50, moving to the "30 Days of Python" GitHub repo, and finishing with LeetCode and practical automation projects.
- **Student Perks**: Highlighting the GitHub Student Pack, Cursor Pro, Notion Pro, Figma, and Perplexity Pro for students.

## 5. Marketing and Lead Generation
- **Vane**: A cloud-based LinkedIn Sales Navigator scraper designed to extract leads safely without Chrome extensions.
- **Selling AI to Businesses**: Advice on selling the *outcome* (e.g., more appointments, clearer data) rather than the AI technology itself.

---
## Safe Local Scripts Generated
Based on the content, we have built safe, local, and educational scripts replicating the core concepts:
1. `markitdown_converter.py`: A local script to convert documents to markdown using the official Microsoft MarkItDown library.
2. `rooflo_router.py`: A local demonstration of an LLM router that sends simple tasks to a cheap model and complex tasks to an advanced model.
3. `local_ollama_setup.sh`: A safe bash script to install Ollama and run local open-source models for coding.
4. `resume_optimizer_prompts.md`: The exact prompt chain extracted from the reels for resume optimization.
