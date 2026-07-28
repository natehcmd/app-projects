import os
import glob

results_dir = '/Users/natehoward/AgentDrop-Workspace/results_ab/transcripts/'
output_file = '/Users/natehoward/AgentDrop-Workspace/results_ab/all_transcripts.md'

txt_files = glob.glob(os.path.join(results_dir, '*.txt'))

with open(output_file, 'w') as out_f:
    for txt_file in txt_files:
        filename = os.path.basename(txt_file)
        out_f.write(f'# {filename}\n')
        with open(txt_file, 'r') as in_f:
            out_f.write(in_f.read())
        out_f.write('\n\n')

print(f"Compiled {len(txt_files)} transcripts into {output_file}")
