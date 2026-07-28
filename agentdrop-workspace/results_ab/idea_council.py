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
