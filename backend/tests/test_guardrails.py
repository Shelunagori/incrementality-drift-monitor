"""Unit tests for the numeric grounding check."""

from app.agent.guardrails import check_answer, mentions_hypotheses
from app.agent.tools import ToolRecord

RECS = [
    ToolRecord(
        "T1",
        "get_channel_status",
        {"channel": "meta"},
        {
            "status": "RED",
            "current_iroas": 1.544,
            "score": 72,
            "drift_summary": "Changepoint 2025-05-04: iROAS 2.74 -> 1.95 (-29%)",
            "relative": -0.6,
        },
    ),
    ToolRecord(
        "T2", "get_ledger", {}, {"entries": [{"iroas_estimate": 2.523, "end_date": "2025-02-04"}]}
    ),
]


def test_cited_numbers_pass():
    ans = (
        "Meta is RED with score 72 [T1]. Current iROAS is 1.54 [T1], down from the "
        "2.523 measured on 2025-02-04 [T2]. The effect fell 60% [T1]."
    )
    assert check_answer(ans, RECS).passed


def test_rounding_and_summary_numbers_pass():
    assert check_answer("It moved from 2.74 to 1.95, about -29% [T1].", RECS).passed
    assert check_answer("iROAS is about 1.5 [T1].", RECS).passed


def test_invented_number_fails():
    res = check_answer("Meta's iROAS is 0.42 [T1].", RECS)
    assert not res.passed and "0.42" in res.violations[0]


def test_number_from_wrong_source_fails():
    assert not check_answer("The test measured 2.523 [T1].", RECS).passed


def test_uncited_number_fails():
    res = check_answer("Meta's score is 72.", RECS)
    assert not res.passed and "not cited" in res.violations[0]


def test_unknown_citation_and_date_fail():
    assert not check_answer("Score 72 [T9].", RECS).passed
    assert not check_answer("It changed on 2025-06-01 [T1].", RECS).passed


def test_list_markers_and_text_without_numbers_ok():
    ans = "1. Hypothesis: creative fatigue.\n2. Hypothesis: a competitor launched."
    assert check_answer(ans, RECS).passed
    assert mentions_hypotheses(ans)
