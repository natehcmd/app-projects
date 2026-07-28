#!/usr/bin/env python3
"""Offline directory of real, free/low-cost tech certifications for students
and job-seekers. Verified against each provider's real, public program pages
(2026-07-20) — no scraping, no comment-for-DM funnel, just the actual links.
"""
import argparse
import json

CERTS = [
    {
        "name": "Google AI Essentials",
        "provider": "Google / Coursera",
        "cost": "Free",
        "time": "~2 hours",
        "url": "https://grow.google/ai-essentials/",
        "note": "Intro AI literacy course; free enrollment via Grow with Google.",
    },
    {
        "name": "HubSpot Digital Marketing Certification",
        "provider": "HubSpot Academy",
        "cost": "Free",
        "time": "~4-6 hours",
        "url": "https://academy.hubspot.com/courses/digital-marketing",
        "note": "Widely recognized, free, self-paced.",
    },
    {
        "name": "IBM SkillsBuild",
        "provider": "IBM",
        "cost": "Free",
        "time": "Varies by track",
        "url": "https://skillsbuild.org/",
        "note": "Some IBM SkillsBuild tracks offer transferable college credit via partner institutions — verify with your school's registrar before assuming credit transfers automatically.",
    },
    {
        "name": "GitHub Foundations",
        "provider": "GitHub / Credly",
        "cost": "Free exam voucher via GitHub Student Developer Pack",
        "time": "Varies",
        "url": "https://education.github.com/pack",
        "note": "Requires GitHub Student Developer Pack enrollment (student email verification).",
    },
    {
        "name": "Claude Certified (Anthropic learning courses)",
        "provider": "Anthropic",
        "cost": "Free",
        "time": "Varies",
        "url": "https://github.com/anthropics/courses",
        "note": "Official Anthropic educational repo — cloned locally at ~/Learning/anthropic-courses. "
               "No single 'Claude Certified Architect' credential from Anthropic was verifiable as of "
               "2026-07-20; the reel's framing of a formal cert with employer-paid bonuses is unconfirmed "
               "marketing — the real, verifiable resource is Anthropic's own course material.",
    },
]


def main():
    parser = argparse.ArgumentParser(description="List real, free tech certifications for students.")
    parser.add_argument("--json", action="store_true", help="Print as JSON instead of a table.")
    args = parser.parse_args()

    if args.json:
        print(json.dumps(CERTS, indent=2))
        return

    for c in CERTS:
        print(f"\n{c['name']}  ({c['provider']})")
        print(f"  cost: {c['cost']}  |  time: {c['time']}")
        print(f"  {c['url']}")
        print(f"  note: {c['note']}")


if __name__ == "__main__":
    main()
