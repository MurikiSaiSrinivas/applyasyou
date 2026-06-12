"""Heuristic JD scoring core. Shared by scripts/score_prospects.py and the
sink's auto-score-at-JD-time path, so the logic lives in exactly one place.

Public entry point: score_prospect(row, jd_text, cfg) -> analysis dict.
"""
import re
from datetime import datetime, timezone

from lib.config import (
    stack_keywords, resume_clusters, default_resume, score_thresholds,
)

# Visa / work-authorization kill patterns (US). Generic; edit for other regions.
VISA_KILL_PATTERNS = [
    r"\b(?:must\s+be|require[ds]?|only\s+(?:hiring|consider))\s+(?:a\s+)?u\.?\s?s\.?\s+citizen",
    r"\bu\.?\s?s\.?\s+citizen(?:ship)?\s+(?:is\s+)?(?:required|mandatory|a\s+must)",
    r"\bu\.?\s?s\.?\s+citizens?\s+(?:and|or)\s+(?:green\s+card|permanent\s+resident|lawful\s+permanent)",
    r"\bu\.?\s?s\.?\s+citizens?\s+or\s+permanent\s+residents?\s+only",
    r"\bgreen\s+card\s+holders?\s+only",
    r"\bpermanent\s+resident(?:s)?\s+only",
    r"\bcitizens?\s+of\s+the\s+united\s+states",
    r"\bu\.?\s?s\.?\s+citizen\s+or\s+national",
    r"(?:does\s+not|cannot|will\s+not|unable\s+to|not\s+able\s+to)\s+(?:offer|provide|support|sponsor)\s+(?:visa\s+|work\s+|employment\s+)?(?:sponsorship|visas?)",
    r"\bno\s+(?:visa\s+|work\s+|employment\s+)?sponsorship",
    r"sponsorship\s+(?:is\s+)?not\s+(?:offered|available|provided|possible)",
    r"unable\s+to\s+sponsor",
    r"without\s+(?:current\s+or\s+future\s+)?sponsorship",
    r"no\s+current\s+or\s+future\s+sponsorship",
    r"\b(?:top\s+secret|ts/sci|sci)\s+(?:clearance|with)",
    r"\bsecurity\s+clearance\s+(?:is\s+)?(?:required|needed|necessary|mandatory)",
    r"\bactive\s+(?:secret|top\s+secret|dod|government|federal)\s+clearance",
    r"\bpoly(?:graph)?\s+(?:required|examination|test)",
    r"\bmust\s+(?:be\s+able\s+to\s+)?(?:obtain|hold|pass|possess)\s+(?:and\s+maintain\s+)?(?:a\s+)?(?:secret|top\s+secret|sci|ts\b|polygraph)",
    r"\bitar\b",
    r"\bear\s+(?:restricted|controlled|regulated)",
    r"\bexport\s+control(?:led|s|\s+regulation)",
    r"\bus\s+person\s+(?:status|requirement|only)",
]
VISA_KILL_RE = re.compile("|".join(VISA_KILL_PATTERNS), re.I)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def detect_visa(jd):
    m = VISA_KILL_RE.search(jd)
    if not m:
        return "not_declared", None
    snippet = jd[max(0, m.start() - 10):m.end() + 30].replace("\n", " ")
    return "us_citizen_only", f"visa-kill phrase: {snippet[:80]}"


def count_keyword(text_lc, keyword):
    pattern = r"(?<!\w)" + re.escape(keyword.lower()) + r"(?!\w)"
    return len(re.findall(pattern, text_lc))


def score_stack(jd, keywords, normalizer):
    text_lc = jd.lower()
    total = 0
    hits = []
    for kw, w in keywords:
        if count_keyword(text_lc, kw) > 0:
            total += w
            hits.append(kw)
    pct = min(100, int(total * 100 / normalizer)) if normalizer else 0
    return pct, hits


def pick_resume(jd, clusters, default):
    text_lc = jd.lower()
    votes = {r: sum(count_keyword(text_lc, kw) for kw in kws) for r, kws in clusters.items()}
    if not votes or all(v == 0 for v in votes.values()):
        return default
    return max(votes, key=votes.get)


def summarize_jd_head(jd):
    head = "\n".join(jd.split("\n")[:30])
    out = {}
    m = re.search(r"\$(\d+(?:,\d+)?(?:\.\d+)?)\s*[Kk]?(?:/yr)?\s*-\s*\$(\d+(?:,\d+)?(?:\.\d+)?)\s*[Kk]?", head)
    if m:
        out["comp"] = f"${m.group(1)}K-${m.group(2)}K"
    for wm in ("Remote", "Hybrid", "Onsite", "On-Site", "On Site"):
        if re.search(r"\b" + re.escape(wm) + r"\b", head, re.I):
            out["work_model"] = wm.replace(" ", "").lower()
            break
    return out


def score_prospect(row, jd, cfg):
    """Return the heuristic analysis dict for one prospect, using config."""
    keywords = stack_keywords(cfg)
    clusters = resume_clusters(cfg)
    default = default_resume(cfg)
    thresholds = score_thresholds(cfg)

    visa_signal, visa_note = detect_visa(jd)
    pct, hits = score_stack(jd, keywords, thresholds["normalizer"])
    resume = pick_resume(jd, clusters, default) if visa_signal != "us_citizen_only" else None
    head = summarize_jd_head(jd)

    if visa_signal == "us_citizen_only":
        verdict = "skip"
    elif pct >= thresholds["apply"]:
        verdict = "apply"
    elif pct >= thresholds["maybe"]:
        verdict = "maybe"
    else:
        verdict = "skip"

    note_bits = []
    if "comp" in head:
        note_bits.append(head["comp"])
    if "work_model" in head:
        note_bits.append(head["work_model"])
    if hits:
        note_bits.append(f"stack: {', '.join(hits[:8])}")
    if visa_note:
        note_bits.append(visa_note)
    note = " | ".join(note_bits) if note_bits else "no signals found"

    entry = {
        "verdict": verdict,
        "match_pct": pct,
        "resume": resume,
        "visa_signal": visa_signal,
        "notes": note,
        "analyzed_at": now_iso(),
        "source": "heuristic",
    }
    if verdict in ("skip", "already_applied"):
        entry["dumped_at"] = now_iso()
    return entry
