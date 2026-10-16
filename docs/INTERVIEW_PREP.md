# Interview Preparation

**Author:** Harsha K S

12 questions you should expect for this project, with full answers. Read the **short answer** as the version you say out loud; the rest is backup for follow-ups.

---

## Part A — HR / behavioural

### Q1. "Tell me about this project."

**Short answer:**
> It's an end-to-end poll and survey analysis pipeline. Survey tools export answers, not insights — you get duplicates, blank rows, `N/A`, three different date formats, and then someone has to answer "who's winning and can we trust the number?".
>
> I built a Python pipeline that cleans that raw export, computes vote share with a margin of error, breaks the results down by region and demographics, and outputs ten charts, an insight report, and an interactive Streamlit dashboard. I also wrote a test suite that runs the pipeline and a headless dashboard smoke test.
>
> The biggest thing I learned is that the interesting part isn't the charts — it's the two bugs I only found because I deliberately dirtied the data.

**Follow-up ready:** "What were those bugs?" → see Q10.

---

### Q2. "Why did you choose this project?"

> Poll data is one of the few domains where a small cleaning mistake changes the headline conclusion — if you drop the wrong 5% of rows, the leader flips. It forces you to be careful. And results presentation is a real job: the same numbers can be honest or misleading depending on how you present them, so it taught me to always publish the margin of error next to the share.

---

### Q3. "What would you do differently if you started again?"

> Three things:
> 1. **Write the tests first.** I added them at the end and they immediately caught two bugs the pipeline had been hiding.
> 2. **Use a config file, not module constants**, for the poll design. The seed, question weights and noise rates are all in code, which makes it harder to run variations.
> 3. **Add statistical tests earlier.** I have descriptive comparisons between regions; a chi-square test would tell me whether those differences are real, and it would be a natural next commit.

---

### Q4. "How did you make sure your code is correct?"

> Two layers. First, 15 pipeline tests that assert real invariants: shares must total 100% per question, no duplicate or blank answer may survive cleaning, every option must belong to its question's option set, daily response volume must reconcile with the row count, and the margin-of-error formula must match the hand calculation for a known n.
>
> Second, a headless Streamlit smoke test using `AppTest` — it renders the whole dashboard and asserts it raises zero exceptions. That test caught a bug I'd never have found by eye: two identical Plotly figures rendered in different tabs raised a `StreamlitDuplicateElementId` error.

---

## Part B — Technical

### Q5. "Walk me through your data pipeline."

> Five stages, one command (`python main.py all`):
>
> 1. **Generate** — a synthetic poll: 1,200 respondents, 5 questions, demographic weights, plus deliberate tilt (Candidate A gets +45% weight in the North) so the breakdowns have a real structure to find.
> 2. **Clean** — dedupe, strip whitespace, canonicalise casing, drop blank/junk answers, validate options against each question's option set, parse three date formats, fill missing demographics with an explicit label. Output: a cleaned CSV plus a data-quality report.
> 3. **Analyse** — vote counts, share %, leader, runner-up, lead margin, margin of error, cross-tabs by region/age/gender/device/channel, daily trend, word frequencies.
> 4. **Visualise** — ten matplotlib/seaborn PNGs.
> 5. **Insights** — a Markdown report with an executive summary, per-question tables, demographic deep dive, and recommended actions.

---

### Q6. "How do you calculate option share, and what's the denominator?"

> Votes for an option divided by the **valid answers to that question**, times 100. The denominator is per question, not per response, because questions can be optional — so Q1 might have 1,119 answers and Q2 1,128 out of 5,632 total responses. I compute it per question so that the shares always total exactly 100%, and I state the denominator in every output. Using the total response count instead would have made the shares meaningless.

---

### Q7. "How did you handle the margin of error?"

> Normal approximation: `z × sqrt(p(1−p)/n)` with z = 1.96 for 95%. For Q1, 33.8% of 1,119 gives about ±2.8 points.
>
> The important part is what I *do* with it: I compare the lead margin against it. On Q2 the lead was 1.2 points with a MoE of ±2.6 — so the report says explicitly that Q2 is a statistical tie rather than naming a winner. That's the difference between a chart and an analysis.

---

### Q8. "How did you clean the data? What was in there?"

> I injected the defects deliberately so cleaning wasn't theoretical:
>
> - **Duplicate rows** — `drop_duplicates()`, and I do it **twice** (see Q10).
> - **Whitespace** — `.str.strip()` on every text column.
> - **Casing** — case-insensitive lookup against the canonical option list, so `candidate a - aarav` maps back to `Candidate A - Aarav`. I never "fix" by lowercasing everything, because that destroys the label.
> - **Junk answers** — a token blocklist (`N/A`, `test`, `-`, `1234`) plus emptiness → drop the row.
> - **Option validation** — after canonicalising, I check each answer is in the question's option set and drop the ones that aren't.
> - **Dates** — three formats, so ISO first then a day-first fallback applied *only* to rows ISO failed on.
> - **Missing demographics** — filled with `Unknown` / `Prefer not to say` rather than dropped, so group-by totals stay honest.
>
> Result: 6,180 raw rows → 5,632 valid responses, 91.1% retention, 163 duplicates removed.

---

### Q9. "You said your data is synthetic. Doesn't that make the project fake?"

> The pipeline is real; only the data is synthetic — which is the honest choice when you don't have access to a real survey system. What matters is that the synthetic data has the *same defects and the same structure* as a real export: it's dirty in the specific ways Google Forms exports are dirty, and the demographic relationships are non-uniform (regional and generational tilts), so the analysis has real structure to find rather than noise.
>
> And the dashboard accepts an upload, so anyone with a real CSV — the interview is the obvious place to test that — runs the identical pipeline. I'd rather demonstrate on data I can explain completely than pretend I ran it on something I can't show.

---

### Q10. "What bugs did you find, and how?"

> Two, both found only because the data was deliberately dirty:
>
> 1. **A silent data-corruption bug.** I was injecting mixed date formats by assigning `"14/09/2026"` strings into a `datetime64` column. Pandas silently coerced them back to timestamps, so the mixed formats vanished — the raw file looked clean and the date-parsing code had nothing to do. The fix: cast the column to string *before* overwriting it.
> 2. **A duplicate-detection bug.** `drop_duplicates()` ran first, but a duplicated survey row often differs from its twin only in the date format (`14/09/2026` vs `2026-09-14`), so it isn't an exact duplicate until the dates are parsed. I now dedupe again at the end of the pipeline. Both bugs are documented in `docs/TROUBLESHOOTING.md`.
>
> A third, smaller one: empty free-text cells came back as `NaN` from the CSV, so `astype(str) != ""` was true for every row and the dashboard reported "100% left written feedback" instead of 44.8%. Fixed with a single loader that re-asserts `""`.

---

### Q11. "How would you scale this / handle a much bigger dataset?"

> The current design is vectorised pandas, so it scales to a few million rows without changes. Beyond that:
> - **I/O becomes the bottleneck** — I'd read with `dtype` specified and chunked reads instead of inferring types.
> - **Aggregations** would move to DuckDB or Polars for out-of-core group-bys, with the same pandas API surface.
> - **Dashboard** — cache the analysis bundle (I already do, keyed on a dataset fingerprint) and pre-aggregate for the chart layer rather than filtering raw rows on every interaction.
> - **Repeatability** — the dataset is generated with a fixed seed, so every result in the README is reproducible, which is what makes it debuggable at scale.

---

### Q12. "How do you know your charts are honest?"

> Concretely:
> - Bars start at zero — never a truncated axis to exaggerate a difference.
> - Percentages are computed on **valid** responses, and the denominator is stated on the chart.
> - Shares always total 100% per question, and I test that.
> - The margin of error is printed next to the leader's share, and the report flags any lead smaller than the MoE as a statistical tie.
> - Where I aggregate (regions, age groups), I show within-group share (%) rather than raw counts, because the groups have different sizes.
> - The stacked chart uses a fixed palette with labels only on slices large enough to read — no unreadable slivers.

---

## One-line HR explanation (memorise this)

> "Poll Results Visualizer is an end-to-end pipeline that takes a messy survey export, cleans and validates it, calculates vote shares with a margin of error, breaks the results down by region and demographics, and presents everything as ten charts plus an interactive Streamlit dashboard — built with Python, Pandas, Plotly and Streamlit, and covered by 15 automated tests."

## One-line technical explanation

> "A five-stage ETL + analytics pipeline (`generate → clean → analyse → visualise → insight`) over long-format poll data, with validated categoricals, per-question percentage aggregation, 95% margin-of-error statistics, cross-tab breakdowns and stop-word-free frequency analysis, exposed both as a CLI and a Streamlit app."
