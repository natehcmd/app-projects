#!/usr/bin/env python3
"""
App Stage Advisor
==================

The source reel ("Vibing an app is not hard. Growing an app ain't easy.
Scaling one though, good luck. Stop thinking you can do this on your own,
because you can't.") is a hype hook, not a tutorial — it names three stages
of building an app (vibe-coding a prototype, growing an audience/usage,
scaling infrastructure/team) but gives no method for telling which stage
you're actually in or what to do about it.

This tool fills that gap: you answer a handful of concrete questions about
your app, and it tells you (a) which of the three stages you're really in,
(b) the specific risks people hit at that stage, (c) a checklist of next
moves, and (d) which roles/help you likely can't substitute for solo — the
part the reel gestures at with "you can't do this on your own."

No API keys, no network calls, no dependencies beyond the Python 3 standard
library.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict


@dataclass
class Inputs:
    mau: int                # monthly active users
    mom_growth_pct: float    # month-over-month user growth, percent
    monthly_revenue: float   # USD
    team_size: int           # people actively working on it (including you)
    infra_pain: int          # 1-5 self-rated: outages, slow queries, on-call stress
    churn_pct: float         # monthly churn, percent


@dataclass
class Diagnosis:
    stage: str
    reason: str
    risks: list
    checklist: list
    cant_do_alone: list


def diagnose(i: Inputs) -> Diagnosis:
    # --- SCALING: real load, real money, real breakage risk ---
    if i.mau >= 10_000 or i.monthly_revenue >= 10_000 or i.infra_pain >= 4:
        reason = (
            f"{i.mau:,} MAU, ${i.monthly_revenue:,.0f}/mo revenue, and an "
            f"infra-pain rating of {i.infra_pain}/5 mean failures now have "
            f"real cost — downtime loses money and trust, not just pride."
        )
        risks = [
            "A single-region / single-instance failure takes down paying users.",
            "On-call falls on one person (burnout, slow incident response).",
            "Support volume outgrows what one person can triage.",
            "Ad-hoc infra decisions from the prototype era don't hold under load.",
            f"Churn at {i.churn_pct:.1f}%/mo compounds — growth can mask a leaky bucket.",
        ]
        checklist = [
            "Write (or write down) a basic incident response runbook.",
            "Add monitoring + alerting for the top 3 failure modes you've already hit.",
            "Set an explicit SLA/SLO for uptime, even an informal internal one.",
            "Automate your deploy and rollback path — no more manual scaling steps.",
            "Instrument churn by cohort so you know *why* people leave, not just that they do.",
            "Put a second person on-call rotation, even part-time.",
        ]
        cant_do_alone = [
            "Infrastructure/SRE help — someone who's run production systems under load before.",
            "Customer support coverage once ticket volume passes what you can answer same-day.",
            "A second engineer for code review and incident coverage (bus-factor of 1 is a real risk).",
        ]
        stage = "Scaling"

    # --- GROWING: users are showing up and sticking, but not yet breaking things ---
    elif i.mau >= 100 and i.mom_growth_pct > 0:
        reason = (
            f"{i.mau:,} MAU with {i.mom_growth_pct:.1f}% MoM growth means real "
            f"people are using this beyond you and your friends, but infra pain "
            f"({i.infra_pain}/5) and revenue (${i.monthly_revenue:,.0f}/mo) are "
            f"still low — the challenge is retention and reach, not breakage."
        )
        risks = [
            f"Churn of {i.churn_pct:.1f}%/mo can quietly cancel out your growth rate.",
            "No repeatable acquisition channel — growth is one-off (a post, a mention).",
            "Onboarding isn't tested on people who don't already know how the app works.",
            "You're the only support channel and it doesn't scale past a few dozen users/day.",
        ]
        checklist = [
            "Talk to 5 users who churned in the last 30 days — find the actual reason.",
            "Pick ONE acquisition channel and run it for 4 weeks before judging it.",
            "Simplify onboarding until a stranger can get to value in under 2 minutes.",
            "Set up basic analytics (funnel + retention curve) if you don't have it yet.",
            "Ask 3 active users what they'd be disappointed to lose — that's your core value prop.",
        ]
        cant_do_alone = [
            "An outside perspective on onboarding — you're too close to see the confusing parts.",
            "Someone to own support/community so you can keep building.",
            "A design or copy pass from someone who isn't you — first impressions compound.",
        ]
        stage = "Growing"

    # --- VIBING: prototype stage, few or no real users yet ---
    else:
        reason = (
            f"With {i.mau:,} MAU and ${i.monthly_revenue:,.0f}/mo revenue, this "
            f"is still prototype territory — the job right now is proving someone "
            f"other than you wants this, not scaling anything."
        )
        risks = [
            "Polishing features nobody asked for instead of shipping to real users.",
            "No feedback loop — building in a vacuum for weeks at a time.",
            "Skipping the boring parts (auth, error states, empty states) that make it usable by others.",
        ]
        checklist = [
            "Ship to 10 real people outside your friend group this week.",
            "Cut scope until you can demo the core loop in under 60 seconds.",
            "Add the bare minimum error/empty states so it doesn't look broken on first use.",
            "Set up one feedback channel (a form, a DM, anything) and actually read it.",
            "Decide the one metric that tells you if this is working (signups, return visits, etc.).",
        ]
        cant_do_alone = [
            "Honest outside feedback — friends and family will be too nice to tell you the truth.",
            "A second set of eyes before you ship to strangers, even just for a sanity check.",
        ]
        stage = "Vibing"

    return Diagnosis(stage, reason, risks, checklist, cant_do_alone)


def render_text(i: Inputs, d: Diagnosis) -> str:
    lines = []
    lines.append(f"App Stage: {d.stage}")
    lines.append("=" * (11 + len(d.stage)))
    lines.append("")
    lines.append(d.reason)
    lines.append("")
    lines.append("Risks at this stage:")
    for r in d.risks:
        lines.append(f"  - {r}")
    lines.append("")
    lines.append("Next-move checklist:")
    for c in d.checklist:
        lines.append(f"  [ ] {c}")
    lines.append("")
    lines.append("What you probably can't do solo right now:")
    for c in d.cant_do_alone:
        lines.append(f"  * {c}")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Diagnose whether your app is Vibing, Growing, or Scaling "
                     "and get a concrete checklist for that stage."
    )
    p.add_argument("--mau", type=int, help="Monthly active users")
    p.add_argument("--growth", type=float, dest="mom_growth_pct",
                    help="Month-over-month user growth, percent (e.g. 15 for 15%%)")
    p.add_argument("--revenue", type=float, dest="monthly_revenue",
                    help="Monthly revenue in USD")
    p.add_argument("--team", type=int, dest="team_size",
                    help="People actively working on the app, including you")
    p.add_argument("--infra-pain", type=int, dest="infra_pain",
                    help="Self-rated infra pain 1 (none) to 5 (constant fires)")
    p.add_argument("--churn", type=float, dest="churn_pct",
                    help="Monthly churn, percent")
    p.add_argument("--json", action="store_true", help="Output JSON instead of text")
    args = p.parse_args(argv)

    # Interactive fallback for any missing values.
    def ask(prompt, cast, default):
        val = input(f"{prompt} [{default}]: ").strip()
        return cast(val) if val else default

    interactive = any(
        getattr(args, f) is None
        for f in ("mau", "mom_growth_pct", "monthly_revenue", "team_size", "infra_pain", "churn_pct")
    )
    if interactive and sys.stdin.isatty():
        mau = args.mau if args.mau is not None else ask("Monthly active users", int, 50)
        growth = args.mom_growth_pct if args.mom_growth_pct is not None else ask("MoM growth %", float, 0)
        revenue = args.monthly_revenue if args.monthly_revenue is not None else ask("Monthly revenue ($)", float, 0)
        team = args.team_size if args.team_size is not None else ask("Team size (incl. you)", int, 1)
        pain = args.infra_pain if args.infra_pain is not None else ask("Infra pain 1-5", int, 1)
        churn = args.churn_pct if args.churn_pct is not None else ask("Monthly churn %", float, 0)
    else:
        mau = args.mau or 0
        growth = args.mom_growth_pct or 0.0
        revenue = args.monthly_revenue or 0.0
        team = args.team_size or 1
        pain = args.infra_pain or 1
        churn = args.churn_pct or 0.0

    inputs = Inputs(
        mau=mau, mom_growth_pct=growth, monthly_revenue=revenue,
        team_size=team, infra_pain=pain, churn_pct=churn,
    )
    diagnosis = diagnose(inputs)

    if args.json:
        print(json.dumps({"inputs": asdict(inputs), "diagnosis": asdict(diagnosis)}, indent=2))
    else:
        print(render_text(inputs, diagnosis))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
