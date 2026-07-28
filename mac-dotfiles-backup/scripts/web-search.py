import os
import sys
import json
import urllib.request
import urllib.parse

def search(query):
    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        print(json.dumps({"error": "BRAVE_API_KEY not set"}))
        return
        
    url = f"https://api.search.brave.com/res/v1/web/search?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key
    })
    
    try:
        with urllib.request.urlopen(req) as response:
            print(response.read().decode('utf-8'))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == '__main__':
    if len(sys.argv) > 1:
        search(sys.argv[1])
    else:
        print(json.dumps({"error": "Usage: python3 web-search.py <query>"}))
