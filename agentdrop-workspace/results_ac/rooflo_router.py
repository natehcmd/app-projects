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
