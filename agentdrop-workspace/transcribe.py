import subprocess
import os

batch_file = '/Users/natehoward/AgentDrop-Workspace/batch_ab'
reels_dir = '/Users/natehoward/AgentDrop-Workspace/reels/'
results_dir = '/Users/natehoward/AgentDrop-Workspace/results_ab/transcripts/'

os.makedirs(results_dir, exist_ok=True)

with open(batch_file, 'r') as f:
    files = [line.strip() for line in f if line.strip()]

for file in files:
    file_path = os.path.join(reels_dir, file)
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        continue
    
    # whisper outputs several files (.txt, .vtt, .srt, etc)
    # output_dir will contain them, prefixed by the original filename (without ext)
    name = os.path.splitext(file)[0]
    out_txt = os.path.join(results_dir, f"{name}.txt")
    
    if os.path.exists(out_txt):
        print(f"Already transcribed: {file}")
        continue
        
    print(f"Transcribing {file}...")
    try:
        subprocess.run([
            'arch', '-x86_64',
            '/Users/natehoward/Library/Python/3.9/bin/whisper', 
            file_path, 
            '--output_dir', results_dir, 
            '--model', 'tiny', 
            '--language', 'en'
        ], check=True)
    except Exception as e:
        print(f"Error transcribing {file}: {e}")

print("Transcription completed.")
