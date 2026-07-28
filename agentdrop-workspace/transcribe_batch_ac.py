import os
import subprocess
import time

batch_file = '/Users/natehoward/AgentDrop-Workspace/batch_ac'
reels_dir = '/Users/natehoward/AgentDrop-Workspace/reels'
results_dir = '/Users/natehoward/AgentDrop-Workspace/results_ac/transcripts'

with open(batch_file, 'r') as f:
    files = [line.strip() for line in f if line.strip()]

whisper_path = '/Users/natehoward/Library/Python/3.9/bin/whisper'

for file in files:
    input_path = os.path.join(reels_dir, file)
    output_prefix = os.path.splitext(file)[0]
    output_file = os.path.join(results_dir, output_prefix + '.txt')
    if os.path.exists(output_file):
        print(f"Skipping {file}, already transcribed.")
        continue
        
    print(f"Transcribing {file}...")
    cmd = [
        'arch', '-x86_64', whisper_path, input_path, 
        '--model', 'tiny', 
        '--output_dir', results_dir,
        '--output_format', 'txt'
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Done {file}")
    except Exception as e:
        print(f"Error on {file}: {e}")
