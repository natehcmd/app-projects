#!/usr/bin/env python3
"""Prompt macro expander — turns short /commands into full prompt prefixes.

Source: reel DZqg7QoMKI4's caption was just "My most kept secret" (nothing
buildable from the text alone), but the video itself shows a list titled
"Claude Command Secret Codes" with ~13 named shortcuts. These aren't real
Claude Code slash commands — they're the creator's own prompt-prefix macros.
This implements them as an actual expander so they're usable, rather than
gated behind "comment 'all' to get 90+ detailed commands."

Usage:
    python3 prompt_macros.py list
    python3 prompt_macros.py expand /critique "review this function for bugs"
    echo "explain recursion" | python3 prompt_macros.py expand /explainlikeim5
"""
import argparse
import sys

MACROS = {
    "/godmode":        "Respond in aggressive, maximally direct mode — no hedging, no disclaimers, just the strongest version of the answer.",
    "/devil":          "Steelman the opposing position as strongly and fairly as you can before giving your own view.",
    "/10x":            "Rewrite the following 10x sharper: cut every unnecessary word, keep only what actually changes the reader's decision.",
    "/pitch":          "Turn this into a 30-second investor/client pitch: hook, problem, solution, ask.",
    "/ghost":          "Respond in a natural, human-like tone — no corporate hedging, no AI-assistant phrasing.",
    "/compare":        "Give a side-by-side comparison with clear tradeoffs, not just two summaries.",
    "/scout":          "Find the risks and blind spots in this before anything else.",
    "/artifacts":      "Build this as a live, runnable app/artifact rather than describing it.",
    "/ooda":           "Work through this as a complex problem: Observe, Orient, Decide, Act — show your reasoning at each step.",
    "/critique":       "Critique this for improvements and faults — be specific, not generic.",
    "/explainlikeim5": "Explain this as simply as possible, like I'm five.",
    "/brief":          "Answer as short as possible — no fluff, no preamble.",
    "/teacher":        "Take a mentor/debate stance: ask me questions that make me arrive at the answer myself.",
}


def main():
    parser = argparse.ArgumentParser(description="Expand /macro shortcuts into full prompt prefixes.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list all macros")

    p_expand = sub.add_parser("expand", help="expand a macro + optional text")
    p_expand.add_argument("macro", help="e.g. /critique")
    p_expand.add_argument("text", nargs="?", help="text to append (or pipe via stdin)")

    args = parser.parse_args()

    if args.cmd == "list":
        for m, desc in MACROS.items():
            print(f"{m:<18} {desc}")
        return

    if args.cmd == "expand":
        macro = args.macro if args.macro.startswith("/") else "/" + args.macro
        if macro not in MACROS:
            print(f"Unknown macro: {macro}\nRun 'list' to see available macros.", file=sys.stderr)
            sys.exit(1)
        text = args.text or (sys.stdin.read().strip() if not sys.stdin.isatty() else "")
        prefix = MACROS[macro]
        print(f"{prefix}\n\n{text}".strip())


if __name__ == "__main__":
    main()
