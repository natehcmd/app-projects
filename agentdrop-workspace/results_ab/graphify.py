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
