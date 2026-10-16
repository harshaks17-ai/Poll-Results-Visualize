# Data Quality Report

**Project:** Poll Results Visualizer v1.0.0 · **Author:** Harsha K S

## Summary

| Metric | Value |
| --- | --- |
| rows_in | 6180 |
| duplicates_removed | 163 |
| invalid_answers_removed | 385 |
| unknown_question_rows_removed | 0 |
| out_of_scope_answers_removed | 0 |
| unparseable_dates | 0 |
| duplicates_after_normalisation | 91 |
| rows_out | 5632 |
| retention_pct | 91.13 |
| date_min | 2026-09-14 |
| date_max | 2026-10-13 |
| respondents | 1200 |
| questions | 5 |

## What was fixed

| Issue | Action taken | Impact |
| --- | --- | --- |
| Exact duplicate exports | `drop_duplicates()` on the full row | Removed 72 rows |
| Duplicates hidden behind formatting | Second `drop_duplicates()` after dates were parsed and labels canonicalised | Removed 91 rows |
| Leading/trailing whitespace | `.str.strip()` on every text column | Allowed answers and regions to match their canonical label |
| Inconsistent casing | Case-insensitive lookup against the canonical option/region lists | Restored mixed-case labels to their correct spelling |
| Blank / junk answers | Dropped rows whose answer matched a junk token or was empty | Removed 385 rows |
| Mixed date formats | ISO first, then `format="mixed"` day-first fallback | 0 unparseable dates |
| Missing demographics | Filled with an explicit `Unknown` / `Prefer not to say` label | Keeps group-by charts honest |
| Wrong dtypes | `satisfaction_score` coerced to numeric, dates to timestamp | Enables trend + scale analysis |

Retention: **91.13%** of the raw export survived cleaning.
