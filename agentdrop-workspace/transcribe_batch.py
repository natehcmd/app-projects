import whisper
import os

model = whisper.load_model("tiny")

with open("batch_aa", "r") as f:
    files = [line.strip() for line in f if line.strip()]

for mp4 in files:
    path = os.path.join("reels", mp4)
    if not os.path.exists(path):
        print(f"Skipping {mp4} (not found)")
        continue
    
    print(f"Transcribing {mp4}...")
    result = model.transcribe(path)
    
    # save transcript
    out_path = f"transcripts_{mp4}.txt"
    with open(out_path, "w") as out_f:
        out_f.write(result["text"])
        
print("Done!")
