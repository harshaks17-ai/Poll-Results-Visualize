"""
Synthetic poll-data generator.

Creates a realistic, *messy* poll export that mimics what you would get from
Google Forms, SurveyMonkey or Qualtrics:

* one row per respondent per question (long / tidy format)
* demographic columns (region, age group, gender, device, channel)
* a 1-5 satisfaction scale
* free-text open feedback
* realistic regional / generational "tilts" so demographic analysis is real
* deliberately injected dirt (duplicates, blanks, casing, whitespace, bad
  values, mixed date formats) so the cleaning stage has genuine work to do
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .utils import ensure_directories, get_logger

LOGGER = get_logger()


# --------------------------------------------------------------------------- #
# Respondent-level demographics
# --------------------------------------------------------------------------- #
def _sample_demographics(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Sample the respondent table (one row per person)."""
    dates = pd.date_range(
        end=pd.Timestamp.today().normalize(), periods=config.POLL_DAYS, freq="D"
    )
    # More responses arrive in the middle of the poll window -> a real trend.
    day_weights = rng.dirichlet(np.ones(config.POLL_DAYS) * 3.0) + 0.4

    respondents = pd.DataFrame(
        {
            "respondent_id": [f"R-{1000 + i}" for i in range(n)],
            "response_date": rng.choice(dates, size=n, p=day_weights / day_weights.sum()),
            "region": rng.choice(config.REGIONS, size=n, p=config.REGION_WEIGHTS),
            "age_group": rng.choice(config.AGE_GROUPS, size=n, p=config.AGE_WEIGHTS),
            "gender": rng.choice(config.GENDERS, size=n, p=config.GENDER_WEIGHTS),
            "device": rng.choice(config.DEVICES, size=n, p=config.DEVICE_WEIGHTS),
            "channel": rng.choice(config.CHANNELS, size=n, p=config.CHANNEL_WEIGHTS),
        }
    )

    # Open feedback only from a subset of respondents.
    has_feedback = rng.random(n) < 0.45
    feedback = rng.choice(config.OPEN_TEXT_TEMPLATES, size=n)
    respondents["open_feedback"] = np.where(has_feedback, feedback, "")
    return respondents


def _option_probabilities(
    question: dict, respondents: pd.DataFrame, n: int, rng: np.random.Generator
) -> np.ndarray:
    """Build an (n_respondents, n_options) probability matrix for a question."""
    k = len(question["options"])
    probs = np.tile(np.asarray(question["weights"], dtype=float), (n, 1))

    # Apply demographic tilts: rows matching the filter get scaled weights.
    for column, value, multipliers in question.get("tilts", []):
        mask = (respondents[column].to_numpy() == value)
        if not mask.any():
            continue
        probs[mask] *= np.asarray(multipliers, dtype=float)

    # Guard against degenerate rows then renormalise so each row sums to 1.
    probs = np.clip(probs, 1e-6, None)
    probs /= probs.sum(axis=1, keepdims=True)
    return probs


def _sample_options(probs: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Vectorised categorical sampling from a row-stochastic matrix."""
    cumulative = np.cumsum(probs, axis=1)
    draws = rng.random((probs.shape[0], 1))
    # First option whose cumulative probability exceeds the draw.
    return np.clip((draws > cumulative).sum(axis=1), 0, probs.shape[1] - 1)


# --------------------------------------------------------------------------- #
# Long-format response table
# --------------------------------------------------------------------------- #
def generate_poll_data(n_respondents: int = config.N_RESPONDENTS) -> pd.DataFrame:
    """Return the synthetic (already slightly dirty) long-format poll table."""
    rng = np.random.default_rng(config.RANDOM_SEED)
    respondents = _sample_demographics(n_respondents, rng)
    n = len(respondents)

    blocks: list[pd.DataFrame] = []
    for question in config.QUESTIONS:
        probs = _option_probabilities(question, respondents, n, rng)
        choice_idx = _sample_options(probs, rng)
        options = np.asarray(question["options"], dtype=object)

        block = respondents.copy()
        block["question_id"] = question["id"]
        block["question"] = question["prompt"]
        block["category"] = question["category"]
        block["option_selected"] = options[choice_idx]
        blocks.append(block)

    data = pd.concat(blocks, ignore_index=True)

    # Satisfaction score (numeric) derived from the 1-5 scale question.
    scale = pd.to_numeric(
        data["option_selected"].str.extract(r"^(\d)", expand=False), errors="coerce"
    )
    data["satisfaction_score"] = scale
    data = data[config.CANONICAL_COLUMNS]

    LOGGER.info(
        "Generated %s rows (%s respondents x %s questions)",
        f"{len(data):,}",
        f"{n_respondents:,}",
        len(config.QUESTIONS),
    )
    return data


# --------------------------------------------------------------------------- #
# Dirty-data injection
# --------------------------------------------------------------------------- #
def inject_noise(data: pd.DataFrame) -> pd.DataFrame:
    """Deliberately dirty the export so the cleaning stage is realistic."""
    rng = np.random.default_rng(config.RANDOM_SEED + 1)
    dirty = data.copy()
    n = len(dirty)

    # 1. Exact duplicate rows (survey tools often export duplicates).
    n_dupes = int(n * config.DIRTY_DUPLICATE_RATE)
    if n_dupes:
        dupe_idx = rng.choice(dirty.index, size=n_dupes, replace=False)
        dirty = pd.concat([dirty, dirty.loc[dupe_idx]], ignore_index=True)

    dirty = dirty.reset_index(drop=True)
    m = len(dirty)

    def random_mask(rate: float) -> np.ndarray:
        return rng.random(m) < rate

    # 2. Blank answers -> NaN.
    mask = random_mask(config.DIRTY_MISSING_RATE)
    dirty.loc[mask, "option_selected"] = np.nan

    # 3. Junk / invalid answers.
    junk = ["N/A", "test", "  ", "-", "Unknown", "1234"]
    mask = random_mask(config.DIRTY_INVALID_RATE)
    dirty.loc[mask, "option_selected"] = rng.choice(junk, size=mask.sum())

    # 4. Inconsistent casing (lower / UPPER / Title).
    mask = random_mask(config.DIRTY_CASE_RATE) & dirty["option_selected"].notna()
    if mask.any():
        styled = (
            dirty.loc[mask, "option_selected"]
            .astype(str)
            .map(lambda value: value.lower() if rng.random() < 0.34
                 else value.upper() if rng.random() < 0.67
                 else value.title())
        )
        dirty.loc[mask, "option_selected"] = styled

    # Region labels also arrive in mixed case.
    mask = random_mask(config.DIRTY_CASE_RATE / 2)
    dirty.loc[mask, "region"] = dirty.loc[mask, "region"].astype(str).str.lower()

    # 5. Padding whitespace.
    mask = random_mask(config.DIRTY_WHITESPACE_RATE)
    dirty.loc[mask, "option_selected"] = "  " + dirty.loc[mask, "option_selected"].astype(str) + " "
    mask = random_mask(config.DIRTY_WHITESPACE_RATE / 2)
    dirty.loc[mask, "region"] = " " + dirty.loc[mask, "region"].astype(str)

    # 6. Mixed date formats - the column must become text *before* overwriting,
    #    otherwise pandas re-coerces "10/01/2026" straight back to a timestamp.
    dates = pd.to_datetime(dirty["response_date"], errors="coerce")
    alt = random_mask(config.DIRTY_DATE_FORMAT_RATE) & dates.notna()
    dirty["response_date"] = dates.dt.strftime("%Y-%m-%d").astype("string")
    alt_dates = dates[alt]
    dirty.loc[alt, "response_date"] = np.where(
        rng.random(alt.sum()) < 0.5,
        alt_dates.dt.strftime("%d/%m/%Y").to_numpy(),      # dd/mm/yyyy
        alt_dates.dt.strftime("%b %d, %Y").to_numpy(),     # "Sep 14, 2026"
    )

    LOGGER.info(
        "Injected noise: %s duplicates, %s blanks, %s junk, %s casing, %s whitespace, %s mixed dates",
        f"{n_dupes:,}",
        int(config.DIRTY_MISSING_RATE * m),
        int(config.DIRTY_INVALID_RATE * m),
        int(config.DIRTY_CASE_RATE * m),
        int(config.DIRTY_WHITESPACE_RATE * m),
        int(alt.sum()),
    )
    return dirty


def save_raw(data: pd.DataFrame, path=config.RAW_CSV_PATH) -> None:
    """Write the raw (messy) export to CSV."""
    ensure_directories()
    data.to_csv(path, index=False)
    LOGGER.info("Raw dataset saved -> %s", path.relative_to(config.PROJECT_ROOT))


def generate_and_save(
    n_respondents: int = config.N_RESPONDENTS,
) -> pd.DataFrame:
    """End-to-end: generate, dirty and persist the raw dataset."""
    clean = generate_poll_data(n_respondents)
    dirty = inject_noise(clean)
    save_raw(dirty)
    return dirty


if __name__ == "__main__":  # pragma: no cover - manual execution
    generate_and_save()
