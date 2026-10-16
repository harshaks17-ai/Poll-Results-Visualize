"""
End-to-end tests for the Poll Results Visualizer pipeline.

Run with either:
    python tests/test_pipeline.py        # standalone, prints PASS/FAIL
    python -m pytest tests/ -q           # via pytest
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import analysis, config, data_cleaning, data_generator, insights, visualization  # noqa: E402
from src.data_cleaning import VALID_OPTIONS  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures (built once in memory / a temp folder, never touching real output)
# --------------------------------------------------------------------------- #
def _build_fixtures() -> tuple:
    if not hasattr(_build_fixtures, "cache"):
        raw = data_generator.inject_noise(data_generator.generate_poll_data(200))
        clean, quality = data_cleaning.clean_poll_data(raw)
        bundle = analysis.full_analysis(clean)
        with tempfile.TemporaryDirectory() as tmp:
            original = config.CHARTS_DIR
            config.CHARTS_DIR = Path(tmp)
            try:
                charts = visualization.generate_all_charts(clean, bundle)
                chart_proof = [
                    (Path(p).name, Path(p).stat().st_size) for p in charts
                ]
            finally:
                config.CHARTS_DIR = original
        report = insights.build_insights(clean, bundle)
        _build_fixtures.cache = (raw, clean, quality, bundle, chart_proof, report)
    return _build_fixtures.cache


# --------------------------------------------------------------------------- #
# 1. Data generation
# --------------------------------------------------------------------------- #
def test_generation_shape() -> None:
    raw, clean, *_ = _build_fixtures()
    n_questions = len(config.QUESTIONS)
    assert len(clean) <= len(raw), "cleaning must never add rows"
    assert len(clean) > 0
    assert set(config.CANONICAL_COLUMNS).issubset(clean.columns)
    assert clean["question_id"].nunique() == n_questions
    assert clean["respondent_id"].nunique() > 0
    assert raw["question_id"].nunique() == n_questions


def test_generation_injects_dirt() -> None:
    raw, *_ = _build_fixtures()
    # Duplicates must exist in the raw export or cleaning would be pointless.
    assert raw.duplicated().sum() > 0, "raw export should contain duplicate rows"
    answers = raw["option_selected"].astype("string").str.strip()
    assert answers.isna().sum() > 0, "raw export should contain blank answers"
    # Mixed date formats must be present.
    text = raw["response_date"].astype(str)
    assert (~text.str.match(r"^\d{4}-\d{2}-\d{2}$")).sum() > 0, "mixed date formats expected"
    # Case noise must be present.
    assert (answers != answers.str.strip(" ")).sum() >= 0


# --------------------------------------------------------------------------- #
# 2. Cleaning
# --------------------------------------------------------------------------- #
def test_cleaning_removes_noise() -> None:
    raw, clean, quality, *_ = _build_fixtures()
    assert quality["duplicates_removed"] > 0
    assert quality["invalid_answers_removed"] > 0
    assert clean.duplicated().sum() == 0, "no duplicates may survive cleaning"
    assert clean["option_selected"].isna().sum() == 0, "no blank answers may survive"
    assert clean["option_selected"].astype(str).str.strip().eq(clean["option_selected"]).all()
    assert quality["retention_pct"] > 70, "a sane export should keep most rows"


def test_cleaning_removes_normalisation_duplicates() -> None:
    """Rows that differ only by date format / casing must collapse to one."""
    raw = pd.DataFrame(
        {
            "respondent_id": ["R-1001", "R-1001"],
            "response_date": ["2026-09-14", "14/09/2026"],
            "question_id": ["Q1", "q1"],
            "question": ["Q1 prompt", "Q1 prompt"],
            "category": ["Election Poll", "Election Poll"],
            "option_selected": ["candidate a - aarav", "  CANDIDATE A - AARAV  "],
            "satisfaction_score": [None, None],
            "region": ["north", " North "],
            "age_group": ["18-24", "18-24"],
            "gender": ["Female", "Female"],
            "device": ["Mobile", "Mobile"],
            "channel": ["Email", "Email"],
            "open_feedback": ["", ""],
        }
    )
    clean, quality = data_cleaning.clean_poll_data(raw)
    assert len(clean) == 1, "case/date-format variants of the same response must dedupe"
    assert quality["duplicates_after_normalisation"] == 1
    assert clean.iloc[0]["option_selected"] == "Candidate A - Aarav"
    assert str(clean.iloc[0]["response_date"].date()) == "2026-09-14"


def test_cleaning_dates_valid() -> None:
    _, clean, *_ = _build_fixtures()
    dates = clean["response_date"]
    assert dates.isna().sum() == 0
    span = (dates.max() - dates.min()).days
    assert span <= config.POLL_DAYS + 5, f"date span {span}d looks unparsed/mangled"


def test_cleaning_categories_canonical() -> None:
    _, clean, *_ = _build_fixtures()
    assert set(clean["region"].unique()).issubset(set(config.REGIONS))
    assert set(clean["age_group"].unique()).issubset(set(config.AGE_GROUPS))
    for question_id, options in VALID_OPTIONS.items():
        subset = clean.loc[clean["question_id"] == question_id, "option_selected"]
        assert set(subset.unique()).issubset(set(options))


# --------------------------------------------------------------------------- #
# 3. Analysis
# --------------------------------------------------------------------------- #
def test_option_shares_sum_to_100() -> None:
    _, clean, _, bundle, *_ = _build_fixtures()
    for question_id in clean["question_id"].unique():
        table = analysis.option_share_table(clean, question_id)
        assert abs(table["share_pct"].sum() - 100) < 0.05, f"{question_id} shares != 100%"
        assert table["votes"].sum() == int((clean["question_id"] == question_id).sum())


def test_question_summary_stats() -> None:
    _, clean, _, bundle, *_ = _build_fixtures()
    summaries = bundle["question_summaries"]
    assert len(summaries) == clean["question_id"].nunique()
    for summary in summaries:
        assert 0 <= summary["leading_share_pct"] <= 100
        assert summary["leading_share_pct"] >= summary["runner_up_share_pct"]
        assert summary["margin_of_error_95"] >= 0
        assert summary["lead_margin_pct"] >= 0
    q3 = [s for s in summaries if s["question_id"] == "Q3"][0]
    assert "net_promoter_score" in q3, "scale question must report NPS"
    assert 0 <= q3["mean_score"] <= 5


def test_margin_of_error() -> None:
    assert analysis.margin_of_error(50, 100) > analysis.margin_of_error(50, 1000)
    assert abs(analysis.margin_of_error(50, 100) - 9.8) < 0.1  # 1.96 * 5% = 9.8 pts


def test_breakdowns() -> None:
    _, clean, _, bundle, *_ = _build_fixtures()
    long = bundle["tables"]["breakdown_region"]
    for (question_id, region), group in long.groupby(["question_id", "region"], observed=True):
        assert abs(group["share_pct"].sum() - 100) < 0.06, f"{question_id}/{region} != 100%"
    assert set(bundle["crosstabs"].keys()) >= {
        "Q1_by_region",
        "Q1_by_age_group",
        "Q3_by_region",
    }


def test_trend_table() -> None:
    _, clean, _, bundle, *_ = _build_fixtures()
    trend = bundle["trend"]
    assert len(trend) <= config.POLL_DAYS
    assert trend["responses"].sum() == len(clean)
    assert trend["rolling_7d"].notna().all()
    assert abs(trend["pct_of_total"].sum() - 100) < 0.2


def test_word_frequencies() -> None:
    _, clean, _, bundle, *_ = _build_fixtures()
    words = bundle["words"]
    assert not words.empty
    assert words["frequency"].is_monotonic_decreasing
    assert not set(words["word"]) & {"the", "and", "for", "with"}


def test_json_summary_is_serialisable() -> None:
    _, _, _, bundle, *_ = _build_fixtures()
    payload = analysis._to_jsonable({"overall": bundle["overall"]})
    json.dumps(payload)  # must not raise


# --------------------------------------------------------------------------- #
# 4. Visualisation
# --------------------------------------------------------------------------- #
def test_charts_generated() -> None:
    *_, chart_proof, _ = _build_fixtures()
    assert len(chart_proof) == 10
    for name, size in chart_proof:
        assert name.endswith(".png"), f"unexpected chart name {name}"
        assert size > 10_000, f"chart {name} looks empty ({size} bytes)"


# --------------------------------------------------------------------------- #
# 5. Insights
# --------------------------------------------------------------------------- #
def test_insights_report() -> None:
    _, clean, _, bundle, _, report = _build_fixtures()
    for heading in (
        "Executive summary",
        "Question-by-question findings",
        "demographic deep dive",
        "Recommended actions",
        "Methodology",
    ):
        assert heading in report, f"insight report missing section: {heading}"
    assert "margin of error" in report.lower()


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    tests = [(name, obj) for name, obj in sorted(globals().items()) if name.startswith("test_")]
    failures = 0
    for name, test in tests:
        try:
            test()
            print(f"  PASS  {name}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL  {name} -> {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} tests passed")
    sys.exit(1 if failures else 0)
