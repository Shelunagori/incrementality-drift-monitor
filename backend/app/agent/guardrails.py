"""Post-check: every number in an answer must be cited and present in the cited tool output.

Rules
- A "number" is any digit run in the answer, including decimals, percentages, money
  ("$1,351,755": "$" and thousands separators are stripped) and dates. Markdown list markers
  ("1. ") and the citation tags themselves are ignored.
- Dates may be written DD-MM-YYYY (the display format the prompt asks for) or ISO; both are
  normalised to ISO and must appear in the cited output. Impossible dates are rejected.
- Each number's sentence must contain at least one citation tag like [T2].
- The number must appear in one of the cited outputs: as a value that rounds to it at the
  answer's precision, as a percentage of such a value (x100), or as its absolute value.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.agent.tools import ToolRecord

CITATION = re.compile(r"\[(T\d+)\]")
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")  # ISO, as tools return dates
ANY_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b|\b(\d{2})-(\d{2})-(\d{4})\b")
NUMBER = re.compile(r"(?<![\w.])[-+]?\$?\d[\d,]*(?:\.\d+)?%?")
LIST_MARKER = re.compile(r"(?m)^\s*\d+[.)]\s+")
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass
class CheckResult:
    passed: bool
    violations: list[str] = field(default_factory=list)


def _walk(obj: Any, nums: list[float], texts: list[str]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, int | float):
        nums.append(float(obj))
    elif isinstance(obj, str):
        texts.append(obj)
        for m in NUMBER.findall(DATE.sub(" ", obj)):
            nums.append(_parse(m)[0])
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk(v, nums, texts)
    elif isinstance(obj, list | tuple):
        for v in obj:
            _walk(v, nums, texts)


def _parse(token: str) -> tuple[float, int, bool]:
    """(value, decimals, is_percent) for a number token."""
    pct = token.endswith("%")
    raw = token.rstrip("%").replace("$", "").replace(",", "")
    decimals = len(raw.split(".")[1]) if "." in raw else 0
    return float(raw), decimals, pct


def _matches(value: float, decimals: int, pct: bool, candidates: list[float]) -> bool:
    tol = 0.5 * 10 ** (-decimals) + 1e-9
    for c in candidates:
        for cand in (c, abs(c), c * 100, abs(c) * 100) if pct else (c, abs(c)):
            if abs(abs(value) - cand) <= tol or abs(value - cand) <= tol:
                return True
    return False


def _to_iso(match: re.Match[str]) -> str | None:
    """ISO form of a YYYY-MM-DD or DD-MM-YYYY match; None if it is not a real date."""
    y, m, d = (
        (match.group(1), match.group(2), match.group(3))
        if match.group(1)
        else (match.group(6), match.group(5), match.group(4))
    )
    try:
        return dt.date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def check_answer(answer: str, records: list[ToolRecord]) -> CheckResult:
    by_id = {r.id: r for r in records}
    violations: list[str] = []
    text = LIST_MARKER.sub("", answer)
    for sentence in SENTENCE.split(text):
        cited = [by_id[c] for c in CITATION.findall(sentence) if c in by_id]
        bogus = [c for c in CITATION.findall(sentence) if c not in by_id]
        violations += [f"citation [{c}] does not match any tool call" for c in bogus]
        body = CITATION.sub(" ", sentence)
        nums: list[float] = []
        texts: list[str] = []
        for r in cited:
            _walk(r.output, nums, texts)
        blob = json.dumps([r.output for r in cited], default=str)
        for match in ANY_DATE.finditer(body):
            d, iso = match.group(0), _to_iso(match)
            if iso is None:
                violations.append(f"date {d} is not a valid date")
            elif not cited:
                violations.append(f"date {d} is not cited")
            elif iso not in blob:
                violations.append(f"date {d} not found in cited output")
        for token in NUMBER.findall(ANY_DATE.sub(" ", body)):
            value, decimals, pct = _parse(token)
            if not cited:
                violations.append(f"number {token} is not cited")
            elif not _matches(value, decimals, pct, nums):
                ids = ",".join(r.id for r in cited)
                violations.append(f"number {token} not found in cited output {ids}")
    return CheckResult(passed=not violations, violations=violations)


def mentions_hypotheses(answer: str) -> bool:
    return bool(re.search(r"hypothes", answer, re.I))
