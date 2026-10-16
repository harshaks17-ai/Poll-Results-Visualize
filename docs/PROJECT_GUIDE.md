# Project Guide — Explanation, Planning & Proof Building

**Author:** Harsha K S

This file is the "student documentation" companion to the README: what the project *is*, how it was *planned and built*, and how to *present it*.

---

# Part 1 — Project explanation

## What is a Poll Results Visualizer?

It is a tool that takes poll/survey responses and turns them into answers people can act on.

**Input:** a raw export of responses — one row per respondent per question — with an answer, a timestamp, and some demographics.

**Output:** who is leading, by how much, where the opinion splits, how it changed over time, what people wrote in their own words, and what to do next.

## Simple explanation (for a non-technical listener)

> You ask 1,200 people five questions. You get back a messy spreadsheet: some rows are duplicated, some answers are blank or nonsense, the dates are written three different ways. You can't answer "so what do people want?" from that spreadsheet.
>
> This tool cleans it, counts the votes properly, works out which answer is winning **and how certain we can be**, splits the results by region and age group, and shows all of it as charts and a dashboard you can actually click through.

## Technical explanation (for a technical listener)

> It's a five-stage pipeline over long-format poll data (`respondent_id × question_id × option`):
>
> 1. **Ingest** — synthetic generation *or* CSV upload, with the same schema as a Google Forms export.
> 2. **Clean** — dedupe (run twice, because format-only differences only appear after normalisation), whitespace/casing canonicalisation, junk-answer removal, option-set validation, and multi-format date parsing.
> 3. **Analyse** — per-question percentage aggregation on *valid* answers, leader/runner-up identification, 95% margin of error via the normal approximation, cross-tabs by demographic dimension, daily trend with rolling mean, and stop-word-free text frequency counting.
> 4. **Visualise** — matplotlib/seaborn for reproducible PNGs, Plotly for the interactive layer, one shared design token palette.
> 5. **Present** — a Markdown insight report with recommendations, plus a 6-tab Streamlit app with filters, KPI tiles and CSV export.

## Why it matters

| Without it | With it |
| --- | --- |
| Raw CSV sits in a folder and someone guesses | A number you can defend, with its uncertainty attached |
| "60% are satisfied" | "61.4% promoters vs 18.8% detractors, net +42.6, mean 3.63/5" |
| "Option A won" | "Option A leads by 3.9 points with a ±2.8 MoE — report as close; Option B's lead is inside the noise" |
| One national average | Region splits showing a 19.8-point swing |
| Nobody reads the free text | Top themes extracted and prioritised automatically |

## How organisations use this

- **Election/exit polling** — track candidate support, quantify the lead's reliability, plan region-specific campaigning.
- **Customer feedback (NPS/CSAT)** — convert a 1–5 scale into promoters/detractors and measure the net score per channel.
- **Employee satisfaction surveys** — find which department is the outlier, measure whether an initiative moved the score.
- **Product preference analysis** — rank feature demand and see how it differs by age group and device.
- **Event / classroom feedback** — see what worked, with what certainty, from a small sample.

## The workflow

```
poll data input  ──►  preprocessing  ──►  analysis  ──►  visualisation  ──►  insights  ──►  decision
      │                   │                 │               │                  │              │
      │                   │                 │               │                  │              │
  raw CSV /            clean,          percentages,      charts,           executive       which feature,
  Google Forms         validate,       comparisons,      dashboards,       summary,        which campaign,
  export               groupby         margins           tables            recommendations next poll fix
```

---

# Part 2 — Tech stack options

## Option A — Easy (beginner, ~2 days)

| Aspect | Detail |
| --- | --- |
| Tools | Python, Pandas, Matplotlib, Jupyter |
| Output | static PNG charts + a notebook |
| Dashboard | ✗ none |
| Statistics | plain percentages |
| Difficulty | ⭐ |

**Use it when:** you're learning Pandas for the first time and want something working fast.
**Skip it if:** you want the project to impress — a notebook alone reads as coursework, not a product.

## Option B — Intermediate (recommended, ~5 days) ✅ **selected**

| Aspect | Detail |
| --- | --- |
| Tools | Python, Pandas, NumPy, Matplotlib, Seaborn, **Plotly**, **Streamlit**, Pytest |
| Output | 10 charts + JSON summary + Markdown insight report + interactive dashboard |
| Dashboard | ✓ 6-tab Streamlit app with filters, KPI tiles, CSV upload |
| Statistics | percentages, lead margin, 95% margin of error, NPS, cross-tabs |
| Difficulty | ⭐⭐⭐ |

**What it adds over A:** a real UI, statistical rigour, automated tests, and a modular `src/` package instead of one long notebook.

## Option C — Advanced (enterprise, ~3 weeks)

| Aspect | Detail |
| --- | --- |
| Tools | Option B + FastAPI, PostgreSQL/DuckDB, Airflow, Docker, Power BI/Tableau, scikit-learn, transformers |
| Output | REST API, warehouse, scheduled ETL, BI dashboard, ML sentiment/topic models |
| Dashboard | BI tool + web |
| Statistics | significance testing, survey weighting, clustering, LLM sentiment |
| Difficulty | ⭐⭐⭐⭐⭐ |

**Use it when:** you need to demonstrate data engineering or production deployment for a specific role.

## Why Option B is selected

1. **Highest signal for the effort.** The dashboard and tests are what make a reviewer believe the analysis is real — everything else is footnotes.
2. **Right difficulty for placements.** It shows modular code, statistics, testing and UI — the four things a data-analyst interview touches on.
3. **Runs anywhere.** One `pip install -r requirements.txt`, no database, no Docker, no cloud bill. A recruiter can run it in four commands.
4. **It scales into Option C cleanly.** The modules map 1:1 onto production components: `data_generator`→ingest, `data_cleaning`→ETL, `analysis`→metrics layer, `dashboard`→presentation. So the project can credibly be labelled "MVP of a production pipeline".

---

# Part 3 — Architecture

## Input schema

| Column | Type | Purpose |
| --- | --- | --- |
| `respondent_id` | str | dedupe and grouping key |
| `response_date` | timestamp | trend analysis |
| `question_id` | str | separates the five polls |
| `question` | str | the prompt, for chart titles |
| `category` | str | groups questions by type |
| `option_selected` | str | the answer being counted |
| `satisfaction_score` | int | numeric scale (1–5) for NPS |
| `region`, `age_group`, `gender`, `device`, `channel` | str | breakdown dimensions |
| `open_feedback` | str | free text for frequency analysis |

## Processing

1. **Cleaning** — the gate nothing passes through unvalidated.
2. **Grouping/aggregation** — `groupby(question_id)` and `groupby(dimension, option)`.
3. **Percentage calculation** — `votes / valid answers per question × 100`.
4. **Comparative analysis** — cross-tabs, within-group share, vs-national-average deltas.

## Output

- 10 static charts (`outputs/charts/`)
- `analysis_summary.json` (machine-readable)
- `insights_report.md` (human-readable, with recommendations)
- `data_quality_report.md` (audit trail of what was changed)

## Data-flow explanation

```
data_generator  ──►  data/raw/poll_responses_raw.csv   (6,180 rows, dirty)
                         │  load_raw()
                         ▼
data_cleaning   ──►  data_processed/...clean.csv       (5,632 rows, validated)
                         │  clean_poll_data()
                         ▼
analysis       ──►  bundle{tables, crosstabs, trend, words, summaries}
                    │                │
        ┌───────────┘                └─────────────┐
        ▼                                          ▼
visualization                             insights
 10 PNG charts                             Markdown report
        │                                          │
        └──────────────►  dashboard.py  ◄──────────┘
                    (Streamlit: filters, KPIs, Plotly)
```

---

# Part 4 — Phase-wise implementation plan

### Phase 1 — Setup (Day 1)
- **Do:** folder structure, `requirements.txt`, `src/config.py` (palette + paths), `.gitignore`, virtual env.
- **Why:** shared config means one change updates every module; the folder structure is what makes a repo look professional before anyone runs the code.
- **Output:** `python main.py --help` works, imports resolve.
- **Mistakes to avoid:** installing packages globally instead of in a venv; making `data/`, `outputs/` and `images/` from scratch later (they must exist in the first commit).

### Phase 2 — Data creation (Day 2)
- **Do:** `data_generator.py` — demographics, 5 questions, weighted sampling, demographic tilts, **deliberate dirt**.
- **Why:** without realistic dirt, the cleaning stage is untested theatre. Tilts give the demographic analysis real structure to find.
- **Output:** a raw CSV that looks like a genuine export.
- **Mistakes to avoid:** making the data uniformly random (breaks every breakdown); forgetting to seed (results change every run, so the README goes stale).

### Phase 3 — Cleaning (Day 3)
- **Do:** `data_cleaning.py` — the 10-step pipeline, plus the data-quality report.
- **Why:** every downstream number depends on this being correct; the quality report is your audit trail in an interview.
- **Output:** cleaned CSV + retention %.
- **Mistakes to avoid:** deduping *before* parsing dates (see `docs/TROUBLESHOOTING.md` #3); "fixing" casing by lowercasing everything (destroys the label); dropping rows with missing demographics instead of labelling them.

### Phase 4 — EDA + analysis (Day 4)
- **Do:** `analysis.py` — shares, MoE, breakdowns, trend, word frequency. Then the notebook.
- **Why:** the notebook is how a reviewer verifies you understood the data, not just the API.
- **Output:** JSON summary + headline numbers.
- **Mistakes to avoid:** dividing by the total response count instead of per-question valid answers; presenting a lead without its margin of error.

### Phase 5 — Visualization (Day 5, part 1)
- **Do:** `visualization.py` — 10 charts, one palette, no chart-junk.
- **Why:** charts are the deliverable a non-technical reader judges the project on.
- **Output:** 10 PNGs.
- **Mistakes to avoid:** truncated bar axes; 3-D or rainbow palettes; unreadable pie slices with 12 categories; plotting raw counts when the groups have different sizes.

### Phase 6 — Insights + dashboard (Day 5, part 2)
- **Do:** `insights.py` + `dashboard.py`.
- **Why:** the report converts numbers into a recommendation; the dashboard proves the analysis is reusable.
- **Output:** insight report, running dashboard.
- **Mistakes to avoid:** duplicating chart logic in the dashboard (keep one function per chart, used by both); skipping the data tab and download button (they're what make it feel like a tool).

### Phase 7 — Tests + docs + push (Day 5, part 3)
- **Do:** `tests/`, README, docs, commit and push.
- **Why:** tests let you change the pipeline without fear; the README *is* the project for most reviewers.
- **Output:** public GitHub repo.
- **Mistakes to avoid:** committing `.venv/`; README images with broken paths; no `.gitignore`.

---

# Part 5 — Proof-building plan (5 days)

| Day | Goal | Deliverable | Proof to capture |
| --- | --- | --- | --- |
| **1** | Setup | Structure, config, requirements, venv | `Get-ChildItem -Recurse` screenshot; `pip install` output |
| **2** | Dataset | `data_generator.py` + raw CSV | Raw CSV preview in VS Code showing duplicates, blanks and mixed date formats |
| **3** | Cleaning + analysis | Cleaned CSV, quality report, JSON summary | Before/after row counts (6,180 → 5,632); the quality report table; `analysis_summary.json` in the terminal |
| **4** | Charts | 10 PNGs + executed notebook | All 10 charts in `outputs/charts/`; the notebook with saved outputs |
| **5** | Dashboard + upload | Dashboard screenshots + pushed repo | 5 dashboard tab screenshots; the GitHub repo page rendered in the browser |

### Commit per day

```bash
git commit -m "chore: project scaffold, config palette and requirements"
git commit -m "feat: synthetic poll generator with demographic tilts and injected dirt"
git commit -m "feat: cleaning pipeline and data-quality report"
git commit -m "feat: share, margin-of-error and demographic analysis"
git commit -m "feat: 10 charts, insights report, dashboard, tests and docs"
```

Five commits = five days of visible, continuous work. That reads better than one commit with a 400-file diff.

### Screenshot checklist

| # | What to capture | Where it goes |
| --- | --- | --- |
| 1 | Raw CSV preview (dirt visible) | README screenshots |
| 2 | Cleaned CSV preview | README screenshots |
| 3 | Console `python main.py all` output with headline numbers | README results section |
| 4 | Vote/share summary table | README results |
| 5 | Bar chart (option share) | README screenshot grid |
| 6 | Donut chart | README screenshot grid |
| 7 | Region-wise stacked chart | README screenshot grid |
| 8 | Demographic comparison chart | README screenshot grid |
| 9 | Word cloud | README screenshot grid |
| 10 | Final dashboard (each tab) | README dashboard section |
| 11 | GitHub repo page | Portfolio / LinkedIn |

---

# Part 6 — How to talk about it in one minute

> "I built a poll results visualiser: a five-stage Python pipeline that takes a messy survey export, cleans and validates it, computes vote shares with a margin of error, breaks results down by region and demographics, and outputs ten charts plus an interactive Streamlit dashboard.
>
> The part I'm most proud of is the cleaning. Writing the doubles pass twice sounds odd until you realise a duplicated row differs from its twin only by the date format — so it isn't a duplicate until the dates are parsed. I only found that because I deliberately dirtied the synthetic data, the way a real export is dirty.
>
> It's covered by fifteen automated tests plus a headless dashboard smoke test, and it runs from a clean clone in four commands."
