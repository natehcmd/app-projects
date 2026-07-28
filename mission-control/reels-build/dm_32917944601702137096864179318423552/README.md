# Target Job Project Builder

## What this reel was actually about

The saved caption/transcript file for this reel (`dm_32917944601702137096864179318423552.txt`)
was empty (0 bytes), and an earlier pass couldn't transcribe the audio in
this environment. Rather than give up, I re-extracted frames from the
downloaded `.mp4` directly and watched it (whisper/ffmpeg audio path still
isn't cooperating here, but the visuals + burned-in captions tell the whole
story).

It's a comedy skit: a candidate bombs a FAANG interview because his resume
is empty talk ("do you really think... you're not getting this job"). "One
week later" he's back with a portfolio full of real projects (Terraform,
AWS S3, VPC, CodeBuild) and the interviewer is stunned ("you you literally
built everything... how did you do this?"). The reveal: he went to
`learn.nextwork.org`, typed his target job description into an AI box
("get custom projects for your target job") using something like Claude or
ChatGPT, it generated a custom hands-on project plus a free step-by-step
guide, he built it, and the platform turned his finished work into
polished "hands-on documentation" he shared to LinkedIn/recruiters.

This is a real (if lightly disguised) third-party product plug, not a
disclosed technique with evasive/harmful intent, so there's nothing to
decline here — the underlying idea ("turn a job posting into a concrete
practice project, then turn the finished project into a recruiter-ready
write-up") is a genuinely useful, benign workflow. This tool reimplements
that idea standalone, using your own Anthropic API key, with no dependency
on or scraping of nextwork.org.

## What it does

A small two-step CLI:

1. **`generate-project`** — feed it a target job description (as a text
   file). It calls Claude to produce a concrete, hands-on practice project
   (with a numbered step-by-step guide) tailored to the actual skills that
   posting asks for — e.g. "Provision a VPC with Terraform and troubleshoot
   connectivity" for a DevOps posting.
2. **`generate-writeup`** — after you've actually built the project, feed
   it the project plan plus your own notes on what you did. It calls Claude
   to turn that into a short, honest, recruiter-ready write-up: a one-line
   resume-style headline, a LinkedIn-post-length narrative, and a few
   resume bullets — grounded strictly in your notes (it's told not to
   invent tools, metrics, or outcomes you didn't mention).

## Setup

```bash
cd /Users/natehoward/Projects/mission-control/reels-build/dm_32917944601702137096864179318423552
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # your own key, from console.anthropic.com
```

You need your own Anthropic API key (this hits the Claude API directly — it
does **not** use any locally-installed Claude Code session). Nothing else
to install; no scraping, no external accounts, no bot-detection evasion.

## Run it

```bash
# 1. Generate a custom hands-on project from a job description
python3 target_job_project_builder.py generate-project \
  --job-description example_job.txt \
  --out project_plan.md

# ... go build the project for real ...

# 2. Write your own quick notes on what you actually did, e.g. notes.txt:
#      "Set up a VPC with 2 public/2 private subnets in Terraform, wired up
#       an S3 bucket with a bucket policy, debugged a security group rule
#       blocking ICMP between subnets, wrote it all up in a README."

# 3. Turn that into a recruiter-ready write-up
python3 target_job_project_builder.py generate-writeup \
  --project project_plan.md \
  --notes notes.txt \
  --out writeup.md
```

An example job description (`example_job.txt`, a DevOps posting matching
what's shown on-screen in the reel) is included so you can try step 1
immediately.

## Files

- `target_job_project_builder.py` — the CLI, single file, no external
  services beyond the Anthropic API.
- `example_job.txt` — sample job posting to try `generate-project` against.
- `requirements.txt` — one dependency: the `anthropic` Python SDK.

## Notes / limits

- This is intentionally a from-scratch reimplementation of the *idea* in
  the video, not a client for nextwork.org or any other product — no
  scraping, no login automation, no bypassing of any platform's terms.
- The write-up prompt is instructed to stick to what you actually wrote in
  your notes; it's a drafting aid, not a fabrication machine — always
  review before posting anything to LinkedIn or a resume.
- Swap `MODEL` at the top of the script if you want a different Claude
  model.
