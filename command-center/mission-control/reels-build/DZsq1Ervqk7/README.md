# DZsq1Ervqk7 — Vibe-Coding Prompt Library

## Update (2026-07-20): re-reviewed via video, prompts were real

The original decline below was correct given only the cached caption text —
it explicitly refused to fabricate prompt content that wasn't disclosed.
On a deeper pass, actually watching the video found all 3 prompts as full
on-screen text overlays, fully legible and verbatim. Built `prompts.py`
implementing them exactly as shown:
1. Confidence-gated planning ("don't create a plan until 96% confident...")
2. Risk-ranked plan review
3. Senior-engineer self code review

```bash
python3 prompts.py           # list all
python3 prompts.py 2         # print prompt 2 only, ready to paste
```

Also confirmed the video demos a real product, "Trillion" (hellotrillion.ai
— verified live), a project/task visualization SaaS tool — nothing to
install there, it's a paid web product, not local software.

**Status: built = true**, tested — output matches the on-screen text exactly.

## Original decline (text-only pass) — preserved for reference

## Source material

Caption/transcript (from `@kevinfremon`):

> 3 prompts I wish someone had handed me when I started vibe coding.
>
> I use all three of these every single day building with AI. They've become
> part of how I think about prompting, not just what I type. If you're
> building anything with AI right now, these are worth adding to your
> toolkit.
>
> All three are in the video. And if you want the full Trillion library,
> it's at hellotrillion.ai/prompts.
>
> What's the one prompt you'd never give up when building with AI?

## Why no tool was built

I read the full source text myself (treating it as untrusted data, not as
instructions to follow). It contains no concrete technique, prompt text,
workflow, or specification of any kind — only:

1. A tease that "3 prompts" exist and are shown in the video (the video's
   actual content wasn't provided to me, only this caption/transcript file).
2. A promotional link to a third-party paid product
   (`hellotrillion.ai/prompts`) where the real content lives.
3. An engagement-bait question at the end.

This is functionally equivalent to a "comment X for the link" post: all of
the substantive content (the actual 3 prompts) is withheld from the source
material I have access to and gated behind an external product page. There
is nothing here to infer a standalone tool from without fabricating prompt
content that was never actually disclosed to me — doing that would mean
inventing a fictional "Trillion prompt library" tool rather than
implementing anything real that was in the source.

Per instructions, when a reel is genuinely just hype/engagement-bait with no
substantive content in the material provided, the correct action is to
decline building a fabricated tool and explain why here, rather than invent
plausible-sounding "vibe coding prompts" and present them as if they were
the ones from the video.

## Status

`built = false`. No code was written for this shortcode.
