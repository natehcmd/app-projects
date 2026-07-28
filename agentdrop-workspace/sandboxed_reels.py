"""
SANDBOXED REELS ARCHIVE
All generated reel scripts have been safely consolidated here.
None of these will execute automatically. They are wrapped in functions.
"""

def run_forge_loop_agent():
    """
    Original file: results_aa/forge_loop_agent.py
    """
    import openai
    
    def generate(prompt, model="gpt-4"):
        # Mock generation function
        return f"[{model} Output for: {prompt}]"
    
    def forge_loop(task_description, max_loops=3):
        """
        Implements the 'Forge Loop' pattern safely without 3rd party plugins.
        Draft -> Check -> Fix -> Repeat.
        """
        print(f"Starting Forge Loop for task: {task_description}")
        
        # Step 1: Initial Draft
        draft = generate(f"Draft a solution for: {task_description}")
        print(f"\n--- Initial Draft ---\n{draft}")
        
        for i in range(max_loops):
            print(f"\n--- Loop {i+1} ---")
            
            # Step 2: Self-Critique
            critique_prompt = (
                f"Review the following draft against this rubric: Correct, Complete, Clear, Tested.\n"
                f"Draft: {draft}\n"
                f"List any issues and provide a score out of 100."
            )
            critique = generate(critique_prompt)
            print(f"Critique:\n{critique}")
            
            # In a real implementation, you'd parse the score here.
            # If score >= 90 and zero issues, break early.
            
            # Step 3: Fix
            fix_prompt = (
                f"Fix the following draft based on the critique.\n"
                f"Draft: {draft}\n"
                f"Critique: {critique}"
            )
            draft = generate(fix_prompt)
            print(f"Updated Draft:\n{draft}")
            
        print("\n--- Final Polished Output ---")
        print(draft)
        return draft
    
    if __name__ == "__main__":
        forge_loop("Write a secure login function in Python.")


def run_llm_assembly_line():
    """
    Original file: results_aa/llm_assembly_line.py
    """
    import time
    
    def mock_llm_call(model, prompt):
        return f"[{model} Output] Processed: {prompt[:30]}..."
    
    def run_factory(job_description, items_to_process):
        """
        Implements the LLM Assembly Line (Factory) pattern for cost efficiency.
        Sol (High-tier) -> Terra (Mid-tier) -> Luna (Low-tier) -> Sol (Inspection)
        """
        HIGH_TIER = "model-sol-flagship"
        MID_TIER = "model-terra-drafter"
        LOW_TIER = "model-luna-worker"
        
        print("--- Station 1: Spec Generation (High Tier) ---")
        master_spec = mock_llm_call(HIGH_TIER, f"Write master spec and quality bar for: {job_description}")
        print(master_spec)
        
        print("\n--- Station 2: Drafting (Mid Tier) ---")
        draft_template = mock_llm_call(MID_TIER, f"Create structured template based on spec: {master_spec}")
        print(draft_template)
        
        print("\n--- Station 3: Mass Production (Low Tier) ---")
        produced_items = []
        for item in items_to_process:
            result = mock_llm_call(LOW_TIER, f"Apply template to item: {item}")
            produced_items.append(result)
            print(f"Produced: {result}")
            
        print("\n--- Station 4: QA Inspection (High Tier) ---")
        final_batch = []
        for item in produced_items:
            inspection = mock_llm_call(HIGH_TIER, f"Inspect against quality bar: {item}")
            # Assuming all pass in this mock
            final_batch.append(item)
            print(f"Passed Inspection: {item}")
            
        print("\nBatch processing complete!")
        return final_batch
    
    if __name__ == "__main__":
        jobs = ["User A", "User B", "User C", "User D"]
        run_factory("Write personalized cold emails", jobs)


def run_graphify():
    """
    Original file: results_ab/graphify.py
    """
    import os
    import json
    
    def generate_graph(directory, output_file):
        print(f"Generating knowledge graph for {directory}...")
        graph = {
            "nodes": [],
            "edges": []
        }
        
        # Simple mapping of files and directories
        for root, dirs, files in os.walk(directory):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            rel_root = os.path.relpath(root, directory)
            if rel_root == ".":
                rel_root = "root"
                
            graph["nodes"].append({"id": rel_root, "type": "directory"})
            
            for file in files:
                file_id = os.path.join(rel_root, file)
                graph["nodes"].append({"id": file_id, "type": "file"})
                graph["edges"].append({"source": rel_root, "target": file_id, "relation": "contains"})
                
        with open(output_file, 'w') as f:
            json.dump(graph, f, indent=2)
            
        print(f"Graph successfully generated at {output_file}")
        print("This graph reduces token usage by allowing AI to read relationships instead of full codebases.")
    
    if __name__ == "__main__":
        import sys
        target_dir = sys.argv[1] if len(sys.argv) > 1 else "."
        out_file = sys.argv[2] if len(sys.argv) > 2 else "knowledge_graph.json"
        generate_graph(target_dir, out_file)


def run_idea_council():
    """
    Original file: results_ab/idea_council.py
    """
    import sys
    
    def get_council_prompts(idea):
        print("=== THE IDEA COUNCIL ===")
        print(f"Idea: {idea}\n")
        
        print("1. THE BELIEVER")
        print("Prompt: You are the Believer. Make the strongest possible case for why this idea will work. Who desperately needs it? Why is it brilliant?\n")
        
        print("2. THE SKEPTIC")
        print("Prompt: You are the Skeptic. Attack every weak point of this idea. Why will people refuse to pay? What competitor did the founder forget? What is the fatal flaw?\n")
        
        print("3. THE INVESTOR")
        print("Prompt: You are the Investor. You only care about money and ROI. Will this generate real revenue? How fast? What is the business model?\n")
        
        print("4. THE JUDGE")
        print("Prompt: You are the Judge. Read the arguments from the Believer, Skeptic, and Investor. Hand down a single, brutal verdict. Is this worth pursuing or a waste of 6 months?\n")
    
    if __name__ == "__main__":
        idea = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "A subscription service for AI-generated code."
        get_council_prompts(idea)


def run_security_audit():
    """
    Original file: results_ab/security_audit.py
    """
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


def run_local_ollama_setup():
    """
    Original file: results_ac/local_ollama_setup.sh
    """
    # #!/bin/bash
    # # Safe Local Ollama Setup
    # # This script sets up a local environment for running LLM coding agents for free,
    # # as discussed in the "Claude Code local" reel.
    # 
    # echo "Setting up local Ollama environment for open source coding models..."
    # 
    # # Check if Ollama is installed
    # if ! command -v ollama &> /dev/null
    # then
    #     echo "Ollama is not installed. Please install it from https://ollama.com/download"
    #     echo "Or run: curl -fsSL https://ollama.com/install.sh | sh"
    #     exit 1
    # fi
    # 
    # echo "Ollama is installed."
    # 
    # # Model to pull for coding (e.g., qwen2.5-coder or codellama)
    # MODEL_NAME="qwen2.5-coder:7b"
    # 
    # echo "Pulling $MODEL_NAME..."
    # ollama pull $MODEL_NAME
    # 
    # echo "Model pulled successfully."
    # echo "You can now run your local coding agent against this model."
    # echo "Example: ollama run $MODEL_NAME"


def run_markitdown_converter():
    """
    Original file: results_ac/markitdown_converter.py
    """
    #!/usr/bin/env python3
    """
    MarkItDown Local Converter
    This script demonstrates how to safely convert local documents (PDFs, Word, Excel)
    into clean Markdown using Microsoft's MarkItDown library.
    This reduces token usage when feeding documents to LLMs.
    """
    import os
    import sys
    
    try:
        from markitdown import MarkItDown
    except ImportError:
        print("Please install markitdown: pip install markitdown")
        sys.exit(1)
    
    def convert_to_markdown(file_path):
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return
    
        print(f"Converting {file_path} to Markdown...")
        md = MarkItDown()
        try:
            result = md.convert(file_path)
            
            base_name = os.path.splitext(file_path)[0]
            output_path = f"{base_name}.md"
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result.text_content)
                
            print(f"Successfully converted to {output_path}")
        except Exception as e:
            print(f"Error converting file: {e}")
    
    if __name__ == "__main__":
        if len(sys.argv) < 2:
            print("Usage: python markitdown_converter.py <file_to_convert>")
            sys.exit(1)
            
        convert_to_markdown(sys.argv[1])


def run_rooflo_router():
    """
    Original file: results_ac/rooflo_router.py
    """
    #!/usr/bin/env python3
    """
    Rooflo-style Task Router
    Demonstrates routing a user query to different LLM tiers based on complexity,
    saving API costs by not sending simple tasks to expensive models.
    """
    
    def evaluate_complexity(prompt: str) -> str:
        """
        Evaluates the complexity of a prompt to route it.
        In a real agentic framework, a fast LLM or heuristic would do this.
        """
        complex_keywords = ['architect', 'system', 'compile', 'debug', 'refactor', 'orchestrate', 'multi-step']
        
        # Simple heuristic
        if any(keyword in prompt.lower() for keyword in complex_keywords) or len(prompt.split()) > 50:
            return "high"
        return "low"
    
    def route_task(prompt: str):
        complexity = evaluate_complexity(prompt)
        
        if complexity == "high":
            print("[Router] High complexity detected. Routing to Claude 3.5 Sonnet / GPT-4o...")
            # execute_with_advanced_model(prompt)
            print(f"Executing: '{prompt}' on advanced model.")
        else:
            print("[Router] Low complexity detected. Routing to Claude 3.5 Haiku / GPT-4o-mini...")
            # execute_with_fast_model(prompt)
            print(f"Executing: '{prompt}' on fast/free tier model.")
    
    if __name__ == "__main__":
        tasks = [
            "What is the capital of France?",
            "Design a system architecture for a real-time multiplayer game using WebSockets and Redis.",
            "Write a quick regex to validate an email address."
        ]
        
        for t in tasks:
            print("-" * 40)
            route_task(t)


def run_safe_claude_skill_auditor():
    """
    Original file: results_ad/scripts/safe_claude_skill_auditor.py
    """
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


def run_safe_morning_workflow():
    """
    Original file: results_ad/scripts/safe_morning_workflow.py
    """
    import time
    import os
    
    def detect_double_clap():
        # Placeholder for safe local audio processing.
        # In a real scenario, use PyAudio and local amplitude thresholding.
        # We do NOT send audio data to any external API.
        print("Listening for double clap (simulated)...")
        time.sleep(2)
        print("Double clap detected!")
        return True
    
    def run_morning_workflow():
        print("Starting morning workflow...")
        # Safe local actions
        print("- Opening calendar")
        print("- Fetching local notes")
        print("- Displaying system metrics")
    
    if __name__ == "__main__":
        if detect_double_clap():
            run_morning_workflow()


def run_safe_rag_pipeline():
    """
    Original file: results_ad/scripts/safe_rag_pipeline.py
    """
    class LocalVectorDB:
        """
        A safe, local mock of a Vector Database for a RAG pipeline.
        Does not connect to external third-party DBs without explicit consent.
        """
        def __init__(self):
            self.documents = []
    
        def insert(self, text, embedding):
            self.documents.append({"text": text, "embedding": embedding})
    
        def search(self, query_embedding, top_k=3):
            # Mock search returning top_k results
            return self.documents[:top_k]
    
    class SafeRAGPipeline:
        def __init__(self):
            self.db = LocalVectorDB()
            
        def generate_embedding(self, text):
            # Use a local embedding model here (e.g. HuggingFace sentence-transformers)
            # For demonstration, returns a mock vector.
            return [0.1, 0.2, 0.3]
    
        def add_document(self, text):
            vector = self.generate_embedding(text)
            self.db.insert(text, vector)
            print(f"Document added safely to local DB: {text[:20]}...")
    
        def query(self, user_prompt):
            vector = self.generate_embedding(user_prompt)
            results = self.db.search(vector)
            print(f"RAG retrieved {len(results)} contexts.")
            # Proceed to send to local LLM or approved API...
            return results
    
    if __name__ == "__main__":
        rag = SafeRAGPipeline()
        rag.add_document("Safe local setup instructions.")
        rag.query("How to setup locally?")


def run_safe_rate_limiter():
    """
    Original file: results_ad/scripts/safe_rate_limiter.py
    """
    import time
    from collections import defaultdict
    
    class RateLimiter:
        """
        A simple token bucket or time-window rate limiter to prevent the $22K cloud bill scenario.
        """
        def __init__(self, max_requests, time_window_seconds):
            self.max_requests = max_requests
            self.time_window = time_window_seconds
            self.requests = defaultdict(list)
    
        def is_allowed(self, ip_address):
            current_time = time.time()
            # Clean up old requests
            self.requests[ip_address] = [
                req_time for req_time in self.requests[ip_address] 
                if current_time - req_time < self.time_window
            ]
            
            if len(self.requests[ip_address]) < self.max_requests:
                self.requests[ip_address].append(current_time)
                return True
            else:
                return False
    
    if __name__ == "__main__":
        limiter = RateLimiter(max_requests=5, time_window_seconds=10)
        test_ip = "192.168.1.100"
        
        print("Simulating traffic...")
        for i in range(7):
            allowed = limiter.is_allowed(test_ip)
            print(f"Request {i+1}: {'Allowed' if allowed else 'Blocked (Rate Limited)'}")
            time.sleep(0.5)


if __name__ == "__main__":
    print("This is a safe sandbox file. No scripts will run automatically.")
    print("To run a script, import this file or modify the bottom to call a specific function.")
