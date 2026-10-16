"""
Data cleaning / preprocessing stage.

Reads the raw (messy) poll export and returns an analysis-ready table:
whitespace trimmed, casing standardised, duplicates removed, blanks and junk
answers dropped, dates parsed from mixed formats, and dtypes enforced.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .utils import ensure_directories, get_logger

LOGGER = get_logger()

VALID_OPTIONS: dict[str, list[str]] = {q["id"]: list(q["options"]) for q in config.QUESTIONS}
VALID_QUESTIONS: dict[str, str] = {q["id"]: q["prompt"] for q in config.QUESTIONS}
VALID_CATEGORIES: dict[str, str] = {q["id"]: q["category"] for q in config.QUESTIONS}
JUNK_TOKENS = {"n/a", "na", "none", "null", "nan", "test", "-", "--", "?", "", "unknown", "1234"}


# --------------------------------------------------------------------------- #
# Individual cleaning steps
# --------------------------------------------------------------------------- #
def _trim_strings(data: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Strip leading/trailing whitespace from text columns."""
    data[columns] = data[columns].apply(lambda col: col.astype("string").str.strip())
    return data


def _normalise_to_canonical(series: pd.Series, canonical: list[str]) -> pd.Series:
    """Map case/whitespace variants back onto the canonical spelling."""
    lookup = {str(value).strip().casefold(): value for value in canonical}
    cleaned = series.astype("string").str.strip()
    return cleaned.map(lambda value: lookup.get(str(value).casefold(), value))


def _parse_mixed_dates(series: pd.Series) -> pd.Series:
    """Parse dates that arrive as ISO, dd/mm/yyyy or 'Jan 5, 2026' strings.

    ISO is tried first so that valid ISO strings are never re-interpreted
    (a day-first fallback would silently swap "2026-10-02" to 2026-02-10).
    The day-first fallback is applied *only* to rows the ISO pass failed on.
    """
    text = series.astype("string").str.strip()
    parsed = pd.to_datetime(text, format="%Y-%m-%d", errors="coerce")
    remaining = parsed.isna()
    if remaining.any():
        fallback = pd.to_datetime(
            text[remaining], format="mixed", errors="coerce", dayfirst=True
        )
        parsed.loc[remaining] = fallback
    return parsed


def _enforce_dtypes(data: pd.DataFrame) -> pd.DataFrame:
    """Coerce columns to their final, analysis-friendly dtypes."""
    data["respondent_id"] = data["respondent_id"].astype("string").str.upper()
    data["satisfaction_score"] = pd.to_numeric(data["satisfaction_score"], errors="coerce")
    data["question_id"] = data["question_id"].astype("string").str.upper()
    return data


# --------------------------------------------------------------------------- #
# Main pipeline
# --------------------------------------------------------------------------- #
def clean_poll_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Clean the raw poll export.

    Returns the cleaned DataFrame and a data-quality dictionary used for the
    quality report.
    """
    quality: dict[str, object] = {"rows_in": int(len(raw))}
    data = raw.copy()

    # Step 0: tidy column names (exports are rarely snake_case).
    data.columns = [str(col).strip().lower().replace(" ", "_") for col in data.columns]
    quality["columns"] = list(data.columns)

    # Step 1: drop exact duplicates exported twice by the survey tool.
    before = len(data)
    data = data.drop_duplicates()
    quality["duplicates_removed"] = before - len(data)

    # Step 2: normalise whitespace before anything else.
    text_columns = [col for col in data.columns if data[col].dtype == "string" or col not in ("satisfaction_score",)]
    data = _trim_strings(data, text_columns)

    # Step 3: standardise categorical spelling (fixes casing / spacing noise).
    for column, canonical in (
        ("region", config.REGIONS),
        ("age_group", config.AGE_GROUPS),
        ("gender", config.GENDERS),
        ("device", config.DEVICES),
        ("channel", config.CHANNELS),
    ):
        if column in data.columns:
            data[column] = _normalise_to_canonical(data[column], canonical)

    # Step 4: validate the answer column (empty, whitespace or junk -> invalid).
    answer = data["option_selected"].astype("string").str.strip()
    invalid_mask = answer.isna() | answer.str.casefold().isin(JUNK_TOKENS)
    quality["invalid_answers_removed"] = int(invalid_mask.sum())
    data = data.loc[~invalid_mask].copy()

    # Re-trim and re-canonicalise answers now that blanks are gone.
    data["option_selected"] = (
        data["option_selected"].astype("string").str.strip().str.strip('"').str.strip()
    )

    # Step 5: keep only rows belonging to a known question.
    data = _enforce_dtypes(data)
    unknown_question = ~data["question_id"].isin(VALID_QUESTIONS.keys())
    quality["unknown_question_rows_removed"] = int(unknown_question.sum())
    data = data.loc[~unknown_question].copy()

    # Step 6: map answers back to the canonical option spelling per question.
    def _canon_answer(row: pd.Series) -> str:
        lookup = {opt.strip().casefold(): opt for opt in VALID_OPTIONS[str(row["question_id"])]}
        return lookup.get(str(row["option_selected"]).strip().casefold(), str(row["option_selected"]))

    data["option_selected"] = data.apply(_canon_answer, axis=1)

    # Step 7: drop answers that still do not belong to the question's option set.
    valid_answer = data.apply(
        lambda row: str(row["option_selected"]).strip().casefold()
        in {opt.strip().casefold() for opt in VALID_OPTIONS[str(row["question_id"])]},
        axis=1,
    )
    quality["out_of_scope_answers_removed"] = int((~valid_answer).sum())
    data = data.loc[valid_answer].copy()

    # Step 8: dates -> real timestamps.
    data["response_date"] = _parse_mixed_dates(data["response_date"])
    quality["unparseable_dates"] = int(data["response_date"].isna().sum())

    # Step 9: fill remaining demographic gaps with an explicit label.
    for column, label in (
        ("region", "Unknown"),
        ("age_group", "Unknown"),
        ("gender", "Prefer not to say"),
        ("device", "Unknown"),
        ("channel", "Unknown"),
    ):
        if column in data.columns:
            data[column] = data[column].astype("string").fillna(label).replace("", label)
    data["open_feedback"] = data["open_feedback"].astype("string").fillna("")

    # Step 9b: SECOND duplicate pass, run *after* all normalisation.
    # A duplicated survey row often survives the first pass because its twin was
    # written with a different date format ("14/09/2026" vs "2026-09-14") or
    # different casing. Those rows only become exactly identical once dates are
    # parsed and labels canonicalised, so they must be dropped here.
    before = len(data)
    data = data.drop_duplicates()
    quality["duplicates_after_normalisation"] = before - len(data)
    quality["duplicates_removed"] = (
        int(quality.get("duplicates_removed", 0))
        + int(quality["duplicates_after_normalisation"])
    )

    # Step 10: drop rows with no usable date, then finalise dtypes and order.
    data = data.dropna(subset=["response_date"])
    data["response_date"] = pd.to_datetime(data["response_date"])
    data["question"] = data["question_id"].map(VALID_QUESTIONS)
    data["category"] = data["question_id"].map(VALID_CATEGORIES)
    data = data[config.CANONICAL_COLUMNS].sort_values(
        ["response_date", "respondent_id", "question_id"]
    ).reset_index(drop=True)

    quality["rows_out"] = int(len(data))
    kept = len(data) / quality["rows_in"] if quality["rows_in"] else 0.0
    quality["retention_pct"] = round(kept * 100, 2)
    quality["date_min"] = str(data["response_date"].min().date())
    quality["date_max"] = str(data["response_date"].max().date())
    quality["respondents"] = int(data["respondent_id"].nunique())
    quality["questions"] = int(data["question_id"].nunique())

    LOGGER.info(
        "Cleaned %s -> %s rows (%.2f%% retained, %s duplicates dropped)",
        f"{quality['rows_in']:,}",
        f"{quality['rows_out']:,}",
        quality["retention_pct"],
        quality["duplicates_removed"],
    )
    return data, quality


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def load_raw(path=config.RAW_CSV_PATH) -> pd.DataFrame:
    """Load the raw poll export."""
    LOGGER.info("Loading raw dataset -> %s", path.relative_to(config.PROJECT_ROOT))
    return pd.read_csv(path)


def save_clean(data: pd.DataFrame, path=config.CLEAN_CSV_PATH) -> None:
    """Persist the cleaned dataset."""
    ensure_directories()
    data.to_csv(path, index=False)
    LOGGER.info("Clean dataset saved -> %s", path.relative_to(config.PROJECT_ROOT))


def save_quality_report(quality: dict, path=config.QUALITY_MD_PATH) -> None:
    """Write the data-quality report as Markdown."""
    rows = "\n".join(f"| {key} | {value} |" for key, value in quality.items() if key != "columns")
    report = f"""# Data Quality Report

**Project:** {config.PROJECT_NAME} v{config.PROJECT_VERSION} · **Author:** {config.PROJECT_AUTHOR}

## Summary

| Metric | Value |
| --- | --- |
{rows}

## What was fixed

| Issue | Action taken | Impact |
| --- | --- | --- |
| Exact duplicate exports | `drop_duplicates()` on the full row | Removed {quality.get('duplicates_removed', 0) - quality.get('duplicates_after_normalisation', 0)} rows |
| Duplicates hidden behind formatting | Second `drop_duplicates()` after dates were parsed and labels canonicalised | Removed {quality.get('duplicates_after_normalisation', 0)} rows |
| Leading/trailing whitespace | `.str.strip()` on every text column | Allowed answers and regions to match their canonical label |
| Inconsistent casing | Case-insensitive lookup against the canonical option/region lists | Restored mixed-case labels to their correct spelling |
| Blank / junk answers | Dropped rows whose answer matched a junk token or was empty | Removed {quality.get('invalid_answers_removed', 0) + quality.get('out_of_scope_answers_removed', 0)} rows |
| Mixed date formats | ISO first, then `format="mixed"` day-first fallback | {quality.get('unparseable_dates', 0)} unparseable dates |
| Missing demographics | Filled with an explicit `Unknown` / `Prefer not to say` label | Keeps group-by charts honest |
| Wrong dtypes | `satisfaction_score` coerced to numeric, dates to timestamp | Enables trend + scale analysis |

Retention: **{quality.get('retention_pct', 0)}%** of the raw export survived cleaning.
"""
    ensure_directories()
    path.write_text(report, encoding="utf-8")
    LOGGER.info("Data-quality report saved -> %s", path.relative_to(config.PROJECT_ROOT))


def run_cleaning() -> tuple[pd.DataFrame, dict]:
    """Convenience wrapper: load raw -> clean -> persist both artefacts."""
    raw = load_raw()
    clean, quality = clean_poll_data(raw)
    save_clean(clean)
    save_quality_report(quality)
    return clean, quality


if __name__ == "__main__":  # pragma: no cover - manual execution
    run_cleaning()
