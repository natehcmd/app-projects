import os

shortcodes = [
  "DaBNLmpMB5H", "DabxbsRMH5c", "DaC9aW6Miyi", "DaebyH0xIDQ", "DafvMV_Fh-Z", "Dag7fodBTWf",
  "DaHR5JWPLvo", "DaI3LY3tLYn", "DaMauuPAzao", "DaQ1XDsycZP", "DaRbl6qJxRM", "DaWjATqpBjL",
  "DaWV_2pvXCw", "DaYi--upDRH", "DW4Gc3PDibh", "DX7mH5Lii8a", "DXAshxEDM5m", "DXUJ1zdCJaa",
  "DXyvXCNITAK", "DY2EEWZCJ3A", "DY2GRVfN4bZ", "DY8jSEGR0-d", "DYHs8XUvayY", "DYm-E6TMSqV",
  "DZ0rP21xg1V", "DZ5H6F1Rz1S", "DZ5xhLYvGpT", "DZ7eidBvr4F", "DZAn5OBMIcU", "DZAtd2JTvT9",
  "DZc0F3Nx2rb", "DZcSLefuxRU", "DZcwJrJzLLh", "DZCzO6GE0y7", "DZEX2WRgyMu", "DZL7SEANnl_",
  "DZLivf_h_Vm", "DZmuKk7hzoY", "DZn-G9wvwgX", "DZoJOLQoQY2", "DZpgTfBioe6", "DZpySOnOCxI",
  "DZQH-qwurUy", "DZsAeTIsx49", "DZtXWtYsMdS", "DZUKKIBPnnV", "DZVEN4gMRXV", "DZWLmJQuw-7",
  "DZxUGClNzi_", "dm_32917907497864438839677623153459200", "dm_32917933034762484826734332238364672",
  "dm_32917959074832036870973153980973056", "dm_32918487323722414055000287953813504",
  "dm_32918520329325066523799774124048384", "dm_32918520542156645223744792168497152",
  "dm_32919129118491137692822018757492736"
]

reels_dir = os.path.expanduser("~/AgentDrop-Workspace/reels")
out_file = os.path.expanduser("~/AgentDrop-Workspace/56_reels_compiled.txt")

with open(out_file, "w") as out:
    for code in shortcodes:
        # Check if transcript exists (we might have .txt or we might need to check DB)
        txt_path = os.path.join(reels_dir, f"{code}.txt")
        if os.path.exists(txt_path):
            with open(txt_path, "r") as f:
                content = f.read()
            out.write(f"--- REEL {code} ---\n")
            out.write(content.strip() + "\n\n")
        else:
            out.write(f"--- REEL {code} (NOT FOUND) ---\n\n")
