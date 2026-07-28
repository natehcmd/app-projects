import sys
import urllib.request
from bs4 import BeautifulSoup

def scrape(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            html = response.read()
            soup = BeautifulSoup(html, 'html.parser')
            # Extract main text
            for script in soup(["script", "style", "header", "footer", "nav"]):
                script.extract()
            text = soup.get_text(separator=' ', strip=True)
            print(text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        scrape(sys.argv[1])
    else:
        print("Usage: python3 web-scrape.py <url>")
