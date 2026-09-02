#!/usr/bin/env python3
"""
find-skills — search GitHub for Claude Code "skills" that match a task,
ranked by stars (a proxy for "battle-tested"), and print install instructions.

This is a small, honest, standalone version of the idea in the source reel:
"install one skill that finds the right skill for you." Rather than a mystery
one-liner gated behind a DM, this script does the actual work in the open:
it queries the public GitHub Code/Repo Search API for repositories that look
like Claude Code skills and match your query, sorts by stars, and shows you
exactly what it would install (a `SKILL.md`-bearing folder) — you decide
whether to actually clone/copy it. It does not scrape any site, does not
touch install/download counters, does not bypass auth, and does not
auto-install anything without you looking at the result first.

Usage:
    python3 find_skills.py "summarize a pdf"
    python3 find_skills.py "convert csv to json" --limit 5
    python3 find_skills.py "web scraping" --min-stars 10

Setup:
    - Python 3.8+, stdlib only (urllib, json, argparse) — no pip installs.
    - GitHub's Code Search API (/search/code) now requires authentication
      even for public repos — without GITHUB_TOKEN set, that lookup will
      401 and this tool automatically falls back to Repository Search
      instead (works unauthenticated, just less precise about which
      subfolder in a repo actually holds SKILL.md). Set GITHUB_TOKEN (a
      plain "public_repo" read-only PAT is enough) for the more precise
      code-search path and a much higher rate limit.

What it actually does under the hood:
    1. Hits GitHub's public Code Search API (https://api.github.com/search/code)
       for files named `SKILL.md` whose content mentions your query terms —
       this is how real Claude Code skills self-describe themselves.
    2. Falls back to Repository Search (https://api.github.com/search/repositories)
       for repos with "claude-code-skill" / "claude-skill" in their topics or
       description, matching your query terms.
    3. De-dupes by repo, sorts by star count (as a "battle-tested" signal —
       same idea the reel describes, just done transparently), and prints
       the repo, description, stars, and the exact `SKILL.md` path found.
    4. Prints (but does not run) the install command: cloning the repo and
       copying the skill folder into ~/.claude/skills/<name>/.

This tool deliberately stops short of auto-installing anything — you review
the candidates and copy the one you want yourself.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API_ROOT = "https://api.github.com"


def gh_get(path, params):
    url = f"{API_ROOT}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "find-skills-cli")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"[warn] GitHub API request failed ({e.code}) for {path}: {body[:200]}",
              file=sys.stderr)
        return {}
    except urllib.error.URLError as e:
        print(f"[warn] network error calling GitHub API: {e}", file=sys.stderr)
        return {}


def search_skill_files(query):
    """Search for SKILL.md files whose content matches the query."""
    q = f"{query} filename:SKILL.md"
    data = gh_get("/search/code", {"q": q, "per_page": 20})
    return data.get("items", [])


def search_skill_repos(query):
    """Fallback: search repos tagged/described as Claude Code skills."""
    q = f"{query} claude skill in:name,description,topics"
    data = gh_get("/search/repositories", {"q": q, "sort": "stars",
                                            "order": "desc", "per_page": 20})
    return data.get("items", [])


def get_repo_stars(full_name, cache):
    if full_name in cache:
        return cache[full_name]
    data = gh_get(f"/repos/{full_name}", {})
    stars = data.get("stargazers_count", 0)
    cache[full_name] = stars
    return stars


def main():
    parser = argparse.ArgumentParser(
        description="Find the right Claude Code skill on GitHub for a task.")
    parser.add_argument("query", help="what you're trying to do, e.g. 'summarize a pdf'")
    parser.add_argument("--limit", type=int, default=8, help="max results to show (default 8)")
    parser.add_argument("--min-stars", type=int, default=0,
                         help="only show repos with at least this many stars")
    args = parser.parse_args()

    print(f"Searching GitHub for skills matching: {args.query!r}\n")

    star_cache = {}
    candidates = {}  # full_name -> {repo info, skill_path}

    for item in search_skill_files(args.query):
        repo = item.get("repository", {})
        full_name = repo.get("full_name")
        if not full_name:
            continue
        candidates.setdefault(full_name, {
            "full_name": full_name,
            "html_url": repo.get("html_url", ""),
            "description": repo.get("description") or "",
            "skill_path": item.get("path", "SKILL.md"),
        })

    if not candidates:
        # Fall back to repo search if code search found nothing
        # (code search requires auth for some accounts / can be flaky).
        for repo in search_skill_repos(args.query):
            full_name = repo.get("full_name")
            if not full_name:
                continue
            candidates.setdefault(full_name, {
                "full_name": full_name,
                "html_url": repo.get("html_url", ""),
                "description": repo.get("description") or "",
                "skill_path": "SKILL.md",
                "stars": repo.get("stargazers_count", 0),
            })

    if not candidates:
        print("No matching skills found. Try a broader query, or check "
              "GITHUB_TOKEN is set if you're being rate-limited.")
        return

    results = []
    for full_name, info in candidates.items():
        stars = info.get("stars")
        if stars is None:
            stars = get_repo_stars(full_name, star_cache)
        if stars < args.min_stars:
            continue
        info["stars"] = stars
        results.append(info)

    results.sort(key=lambda r: r["stars"], reverse=True)
    results = results[:args.limit]

    if not results:
        print(f"Found candidates, but none met --min-stars {args.min_stars}.")
        return

    for i, r in enumerate(results, 1):
        print(f"{i}. {r['full_name']}  (★ {r['stars']})")
        if r["description"]:
            print(f"   {r['description']}")
        print(f"   {r['html_url']}")
        print(f"   skill file: {r['skill_path']}")
        print()

    top = results[0]
    repo_name = top["full_name"].split("/")[-1]
    print("To install the top match by hand:")
    print(f"  git clone {top['html_url']} /tmp/{repo_name}")
    skill_dir = os.path.dirname(top["skill_path"])
    if skill_dir:
        # We know the exact folder within the repo that holds SKILL.md.
        print(f"  cp -r /tmp/{repo_name}/{skill_dir} "
              f"~/.claude/skills/{os.path.basename(skill_dir)}/")
    else:
        # Repo-search fallback doesn't tell us the skill's subfolder — only
        # that a SKILL.md exists somewhere in the repo, so point at the
        # cloned repo itself rather than fabricate a bogus path.
        print(f"  # skill's exact subfolder wasn't returned by this search mode —"
              f" inspect /tmp/{repo_name} for SKILL.md, then:")
        print(f"  cp -r /tmp/{repo_name} ~/.claude/skills/{repo_name}/")
    print("\n(Review the SKILL.md and any scripts before copying — this tool "
          "only finds and ranks candidates, it never installs anything for you.)")


if __name__ == "__main__":
    main()
