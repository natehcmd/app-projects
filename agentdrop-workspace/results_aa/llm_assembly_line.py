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
