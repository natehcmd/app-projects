import json
import urllib.request
import os
import subprocess

# Mock API request to a local Ollama model to analyze ad performance
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:32b"

def speak(text):
    print(f"Jarvis: {text}")
    subprocess.run(["say", text])

def analyze_ads(campaign_data):
    prompt = f"""
    You are an automated Ad Campaign Manager for a media buying agency.
    Analyze the following ad performance data and output a brief verbal summary of what actions you took 
    (e.g., pausing losers, scaling winners). Respond in the voice of a calm, professional AI assistant (like Jarvis).
    Keep the response under 60 words.

    DATA:
    {json.dumps(campaign_data, indent=2)}
    """
    
    req = urllib.request.Request(OLLAMA_URL, method="POST",
                                 data=json.dumps({"model": MODEL, "prompt": prompt, "stream": False}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            res = json.loads(response.read())
            return res.get("response", "Analysis complete.")
    except Exception as e:
        return "Sir, I am unable to reach the analysis model."

def main():
    # In a real scenario, this data would be fetched from the Meta/Facebook Ads API
    mock_data = [
        {"ad_name": "Street Interview Variant A", "spend": 450, "roas": 3.5, "refunds": 0, "status": "ACTIVE"},
        {"ad_name": "Static Image - Discount", "spend": 120, "roas": 0.8, "refunds": 2, "status": "ACTIVE"},
        {"ad_name": "UGC Review - Trend Build", "spend": 300, "roas": 2.1, "refunds": 0, "status": "ACTIVE"}
    ]
    
    print("Fetching campaign data from Ads API...")
    # Mock logic: if ROAS < 1.0, pause the ad. If ROAS > 3.0, double budget.
    for ad in mock_data:
        if ad["roas"] < 1.0:
            ad["status"] = "PAUSED"
            ad["action"] = "Killed due to low ROAS"
        elif ad["roas"] > 3.0:
            ad["action"] = "Doubled Budget"
            
    # Have the AI summarize the actions
    print("Analyzing actions...")
    summary = analyze_ads(mock_data)
    
    # Speak the summary out loud
    speak(summary)

if __name__ == "__main__":
    main()
