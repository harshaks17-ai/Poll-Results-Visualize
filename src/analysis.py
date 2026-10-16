"""
Analysis engine: aggregation, percentages, breakdowns and statistics.

Everything here is pure pandas - it answers the questions a research analyst
actually asks: who is leading, by how much, where, and among which groups.
"""

from __future__ import annotations

import json
import re
from collections import Counter

import numpy as np
import pandas as pd

from . import config
from .utils import ensure_directories, get_logger

LOGGER = get_logger()

STOPWORDS = {
    "the", "and", "for", "with", "was", "are", "you", "our", "but", "not",
    "all", "can", "has", "have", "very", "too", "its", "from", "that", "this",
    "would", "should", "please", "when", "what", "how", "why", "who", "out",
    "get", "got", "had", "his", "her", "she", "him", "they", "them", "there",
    "here", "just", "more", "most", "some", "any", "one", "two", "also",
}

# Strings that pandas turns into NaN on read but which mean "no answer".
EMPTY_TOKENS = {"", "nan", "none", "null", "<na>"}


def load_clean_data(path=config.CLEAN_CSV_PATH) -> pd.DataFrame:
    """Load the cleaned dataset.

    CSV files cannot store the difference between ``""`` and a missing value, so
    pandas reads every empty free-text cell back as ``NaN``. Re-assert ``""``
    here so downstream string checks behave the same as on fresh data.
    """
    data = pd.read_csv(path, parse_dates=["response_date"])
    data["open_feedback"] = data["open_feedback"].fillna("").astype(str)
    return data


def _clean_feedback(data: pd.DataFrame) -> str:
    """Concatenate free-text answers into one lower-case string."""
    values = [
        str(value).lower()
        for value in data["open_feedback"].fillna("")
        if str(value).strip().casefold() not in EMPTY_TOKENS
    ]
    return " ".join(values)


# --------------------------------------------------------------------------- #
# Core aggregations
# --------------------------------------------------------------------------- #
def option_share_table(data: pd.DataFrame, question_id: str) -> pd.DataFrame:
    """Vote counts and percentage share for a single question."""
    subset = data.loc[data["question_id"] == question_id, "option_selected"]
    total = len(subset)
    counts = subset.value_counts()
    table = pd.DataFrame(
        {
            "votes": counts,
            "share_pct": (counts / total * 100).round(2) if total else 0.0,
        }
    )
    table.index.name = "option_selected"
    table = table.sort_values("votes", ascending=False).reset_index()
    table.insert(0, "question_id", question_id)
    table["rank"] = np.arange(1, len(table) + 1)
    return table


def margin_of_error(share_pct: float, n: int, confidence: float = 0.95) -> float:
    """Approximate 95% (or other) margin of error, in percentage points."""
    if n <= 0:
        return 0.0
    z = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(confidence, 1.96)
    p = share_pct / 100.0
    return round(z * np.sqrt(max(p * (1 - p), 0) / n) * 100, 2)


def question_summary(data: pd.DataFrame, question_id: str) -> dict:
    """Headline statistics for one question (leader, share, MoE, spread)."""
    table = option_share_table(data, question_id)
    total = int(table["votes"].sum())
    winner = table.iloc[0]
    runner_up = table.iloc[1] if len(table) > 1 else winner
    summary = {
        "question_id": question_id,
        "question": data.loc[data["question_id"] == question_id, "question"].iloc[0],
        "category": data.loc[data["question_id"] == question_id, "category"].iloc[0],
        "total_responses": total,
        "unique_options": int(len(table)),
        "leading_option": str(winner["option_selected"]),
        "leading_share_pct": float(winner["share_pct"]),
        "runner_up_option": str(runner_up["option_selected"]),
        "runner_up_share_pct": float(runner_up["share_pct"]),
        "lead_margin_pct": round(float(winner["share_pct"]) - float(runner_up["share_pct"]), 2),
        "margin_of_error_95": margin_of_error(float(winner["share_pct"]), total),
        "top2_share_pct": round(
            float(winner["share_pct"]) + float(runner_up["share_pct"]), 2
        ),
    }

    # Scale questions: report the mean / median score instead of a "winner".
    if question_id in ("Q3",):
        scores = pd.to_numeric(
            data.loc[data["question_id"] == question_id, "satisfaction_score"],
            errors="coerce",
        ).dropna()
        if not scores.empty:
            summary["mean_score"] = round(float(scores.mean()), 2)
            summary["median_score"] = float(scores.median())
            summary["promoters_pct"] = round(float((scores >= 4).mean() * 100), 2)
            summary["detractors_pct"] = round(float((scores <= 2).mean() * 100), 2)
            summary["net_promoter_score"] = round(
                summary["promoters_pct"] - summary["detractors_pct"], 2
            )
    return summary


def breakdown_table(
    data: pd.DataFrame, question_id: str, by: str
) -> pd.DataFrame:
    """Long-format breakdown of option share within each group of `by`."""
    subset = data.loc[data["question_id"] == question_id, [by, "option_selected"]]
    counts = (
        subset.groupby([by, "option_selected"], observed=True)
        .size()
        .rename("votes")
        .reset_index()
    )
    group_totals = counts.groupby(by, observed=True)["votes"].transform("sum")
    counts["share_pct"] = (counts["votes"] / group_totals * 100).round(2)
    counts.insert(0, "question_id", question_id)
    return counts.sort_values([by, "votes"], ascending=[True, False]).reset_index(drop=True)


def crosstab_share(
    data: pd.DataFrame, question_id: str, by: str
) -> pd.DataFrame:
    """Wide table: group rows x option columns, values = within-group share %."""
    long = breakdown_table(data, question_id, by)
    wide = long.pivot(index=by, columns="option_selected", values="share_pct")
    return wide.round(2)


def trend_table(data: pd.DataFrame) -> pd.DataFrame:
    """Daily response volume plus a 7-day rolling average."""
    daily = (
        data.groupby(data["response_date"].dt.date)
        .size()
        .rename("responses")
        .reset_index()
        .rename(columns={"response_date": "date"})
    )
    daily["date"] = pd.to_datetime(daily["date"])
    full_range = pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")
    daily = (
        daily.set_index("date")
        .reindex(full_range)
        .fillna(0)
        .rename_axis("date")
        .reset_index()
    )
    daily["rolling_7d"] = daily["responses"].rolling(window=7, min_periods=1).mean().round(2)
    daily["pct_of_total"] = (daily["responses"] / daily["responses"].sum() * 100).round(2)
    return daily


def channel_performance(data: pd.DataFrame) -> pd.DataFrame:
    """Responses collected and satisfaction by acquisition channel."""
    grouped = data.groupby("channel", observed=True).agg(
        responses=("respondent_id", "count"),
        unique_respondents=("respondent_id", "nunique"),
        avg_satisfaction=("satisfaction_score", "mean"),
    )
    grouped["avg_satisfaction"] = grouped["avg_satisfaction"].round(2)
    grouped["response_share_pct"] = (grouped["responses"] / grouped["responses"].sum() * 100).round(2)
    return grouped.sort_values("responses", ascending=False).reset_index()


# --------------------------------------------------------------------------- #
# Text analysis (open-ended feedback -> dependency-free word cloud input)
# --------------------------------------------------------------------------- #
def word_frequencies(data: pd.DataFrame, top_n: int = 30) -> pd.DataFrame:
    """Count meaningful words in the free-text column."""
    feedback = _clean_feedback(data)
    tokens = re.findall(r"[a-z][a-z'\-]{2,}", feedback)
    counts = Counter(token for token in tokens if token not in STOPWORDS and len(token) > 2)
    frame = pd.DataFrame(counts.most_common(top_n), columns=["word", "frequency"])
    if not frame.empty:
        frame["frequency"] = frame["frequency"].astype(int)
    return frame


# --------------------------------------------------------------------------- #
# Full analysis run
# --------------------------------------------------------------------------- #
def full_analysis(data: pd.DataFrame) -> dict:
    """Run every aggregation and return a bundle of tables + a summary dict."""
    question_ids = sorted(data["question_id"].unique().tolist())
    summaries = [question_summary(data, qid) for qid in question_ids]

    overall = {
        "responses": int(len(data)),
        "respondents": int(data["respondent_id"].nunique()),
        "questions": int(data["question_id"].nunique()),
        "date_from": str(data["response_date"].min().date()),
        "date_to": str(data["response_date"].max().date()),
        "regions": int(data["region"].nunique()),
        "avg_satisfaction": round(float(data["satisfaction_score"].mean()), 2),
        "feedback_with_text_pct": round(
            float(
                data["open_feedback"]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.casefold()
                .isin(EMPTY_TOKENS)
                .eq(False)
                .mean()
                * 100
            ),
            2,
        ),
    }

    bundle: dict = {
        "overall": overall,
        "question_summaries": summaries,
        "tables": {
            "option_share": pd.concat(
                [option_share_table(data, qid) for qid in question_ids], ignore_index=True
            ),
        },
        "words": word_frequencies(data),
        "trend": trend_table(data),
        "channels": channel_performance(data),
    }

    for dimension in ("region", "age_group", "gender", "device", "channel"):
        bundle["tables"][f"breakdown_{dimension}"] = pd.concat(
            [breakdown_table(data, qid, dimension) for qid in question_ids], ignore_index=True
        )
        bundle["crosstabs"] = bundle.get("crosstabs", {})
        for qid in question_ids:
            bundle["crosstabs"][f"{qid}_by_{dimension}"] = crosstab_share(data, qid, dimension)

    LOGGER.info(
        "Analysed %s responses across %s questions (%s respondents)",
        f"{overall['responses']:,}",
        overall["questions"],
        f"{overall['respondents']:,}",
    )
    return bundle


def _to_jsonable(obj):
    """Recursively convert numpy / pandas objects to plain Python types."""
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, pd.DataFrame):
        # reset_index() so cross-tab row labels survive JSON serialisation.
        return json.loads(obj.reset_index().to_json(orient="records"))
    if isinstance(obj, pd.Series):
        return _to_jsonable(obj.tolist())
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return str(obj)
    if isinstance(obj, np.ndarray):
        return _to_jsonable(obj.tolist())
    return obj


def save_analysis(bundle: dict, path=config.SUMMARY_JSON_PATH) -> None:
    """Persist the machine-readable analysis summary."""
    ensure_directories()
    payload = _to_jsonable(
        {
            "overall": bundle["overall"],
            "question_summaries": bundle["question_summaries"],
            "option_share": bundle["tables"]["option_share"],
            "region_crosstab": bundle["crosstabs"].get("Q1_by_region"),
            "top_words": bundle["words"],
            "channels": bundle["channels"],
        }
    )
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    LOGGER.info("Analysis summary saved -> %s", path.relative_to(config.PROJECT_ROOT))


def run_analysis(data: pd.DataFrame | None = None) -> dict:
    """Load cleaned data (if needed), analyse, persist and return the bundle."""
    if data is None:
        data = load_clean_data()
    bundle = full_analysis(data)
    save_analysis(bundle)
    return bundle


if __name__ == "__main__":  # pragma: no cover - manual execution
    run_analysis()
