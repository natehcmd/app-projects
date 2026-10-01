"""Shared pipeline step for scripts (Nate: every model call goes through the
pipeline unless he says otherwise). The local model's text is checked by Gemini
Flash against the source; if rejected, Gemini Pro redoes it with the reason.

    from pipeline_check import verify_or_fix
    text, note = verify_or_fix(task, text, source, redo_prompt)

`note` says honestly what happened: checked / corrected / flagged / not checked.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".local/share/review-pipeline/code-review-pipeline/scripts"))

CHECK = ("You are checking AI-written text before a user sees it.\nTASK: {task}\n"
         "SOURCE IT MUST BE FAITHFUL TO:\n{source}\n\nTEXT:\n{text}\n\n"
         "Reject it if it states anything false or not supported by the source, or doesn't do "
         "the task. Don't reject for style. Do NOT use tools. "
         'Reply with ONLY: {{"ok": true|false, "issue": "..."}}')


def verify_or_fix(task, text, source, redo_prompt, timeout=60):
    try:
        from claude_director import Dispatcher, TokenLedger
        raw = Dispatcher(TokenLedger(), failover=False).call(
            "agy_flash", "verify", CHECK.format(task=task, source=source[:6000], text=text[:4000]),
            timeout=timeout)
        m = re.search(r"\{[^{}]*\"ok\"[^{}]*\}", raw or "", re.S)
        v = json.loads(m.group(0)) if m else {}
    except Exception as e:
        return text, f"not checked ({str(e)[:60]})"
    if v.get("ok") is True:
        return text, "checked by Gemini ✓"
    if v.get("ok") is not False:
        return text, "not checked (no verdict)"
    issue = str(v.get("issue", ""))[:160]
    try:
        redo = Dispatcher(TokenLedger(), failover=False).call(
            "agy_pro", "rewrite", redo_prompt + "\n\nA reviewer rejected an earlier draft because: "
            + issue + "\nFix that. Same format.", timeout=120).strip()
        if redo:
            return redo, "corrected by Gemini: " + issue
    except Exception:
        pass
    return text, "⚠️ Gemini flagged: " + issue
