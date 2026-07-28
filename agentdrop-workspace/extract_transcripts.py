import sqlite3

db_path = "/Users/natehoward/Projects/mission-control/data/mission.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

targets = [
    # Multi-agent
    "DXxQS0AO1Km", "DY_SoPGKv2A", "DZsup8Lx6yQ",
    # Income/Side-hustle
    "DYKSh1iv8nP", "DZoJOLQoQY2",
    # Bait
    "DZ0rP21xg1V", "DZ5xhLYvGpT", "DZAtd2JTvT9", "DZn-G9wvwgX", "DZxUGClNzi_", "DaMauuPAzao", "DaQ1XDsycZP", "DaWjATqpBjL"
]

for t in targets:
    res = c.execute("SELECT topic, transcript FROM reels WHERE id = ?", (t,)).fetchone()
    print(f"--- REEL: {t} ---")
    if res:
        print(f"Topic: {res[0]}")
        print(f"Transcript Snippet:\n{res[1][:500] if res[1] else 'NO TRANSCRIPT'}\n")
    else:
        print("NOT FOUND IN DB\n")

conn.close()
