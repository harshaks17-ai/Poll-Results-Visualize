# Troubleshooting

**Author:** Harsha K S

Every bug and pitfall found while building this project, with the actual fix. These are not hypothetical — each one broke the pipeline at some point.

---

## 1. Environment & setup

### `ModuleNotFoundError: No module named 'pandas'`
Python isn't installed, or the virtual environment isn't activated.
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

### `ModuleNotFoundError: No module named 'src'`
You're running from inside `src/` or `tests/`. Run from the **project root**:
```bash
cd Poll-Results-Visualize
python main.py all
```
(`main.py` and `dashboard.py` both insert the project root into `sys.path`, so root-level invocation always works.)

### A package has no wheel for your Python version (e.g. `wordcloud` on Python 3.14)
**This is why the project has no `wordcloud` dependency.** The word cloud is rendered from word frequencies with a golden-angle layout in `visualization.plot_word_cloud` and `dashboard.chart_words`. If you want the real library, use Python 3.11–3.12 where wheels exist.

### Charts render blank, or `UserWarning: Matplotlib is currently using agg`
Normal in a headless environment. `utils.apply_matplotlib_theme()` calls `matplotlib.use("Agg")` on purpose — it just means figures are saved to files rather than shown. To see them, open the PNGs in `outputs/charts/`.

### `OSError: [Errno 22] Invalid argument` when saving a chart
The output directory doesn't exist. `ensure_directories()` creates all of them; call it first (every `_save()` already does).

---

## 2. Data bugs (the interesting ones)

### Mixed date formats silently disappear
**Symptom:** the raw CSV contains only ISO dates (`2026-09-14`) even though you generated mixed formats, so the date-parsing code has nothing to do and the data-quality report says nothing was fixed.

**Cause:** assigning formatted strings into a `datetime64` column. Pandas coerces them straight back:
```python
dirty.loc[alt, "response_date"] = alt_dates.dt.strftime("%d/%m/%Y")  # "10/01/2026" -> 2026-01-10
```
The column was already a timestamp type, so pandas parsed the string and stored a timestamp. Writing to CSV then produced ISO — the defect was invisible.

**Fix:** cast the column to string *before* overwriting it.
```python
dirty["response_date"] = dates.dt.strftime("%Y-%m-%d").astype("string")
dirty.loc[alt, "response_date"] = np.where(..., alt_dates.dt.strftime("%d/%m/%Y"), ...)
```

### ISO dates get swapped by the day-first fallback
**Symptom:** `2026-10-02` becomes `2026-02-10` — month and day swap.

**Cause:** `pd.to_datetime(text, format="mixed", dayfirst=True)` does **not** leave ISO strings alone; day-first applies to `YYYY-MM-DD` too.

**Fix:** try ISO first, then apply the fallback **only** to the rows that failed.
```python
parsed = pd.to_datetime(text, format="%Y-%m-%d", errors="coerce")
remaining = parsed.isna()
if remaining.any():
    parsed.loc[remaining] = pd.to_datetime(text[remaining], format="mixed", dayfirst=True, errors="coerce")
```

### Duplicated survey rows survive cleaning
**Symptom:** `duplicates_removed` is non-zero, yet the cleaned DataFrame still contains duplicate rows.

**Cause:** a duplicated row often differs from its twin only in the date format (`14/09/2026` vs `2026-09-14`) or in casing. Those rows are not exact duplicates until the labels are canonicalised **and** the dates are parsed. `drop_duplicates()` before normalisation can't see them.

**Fix:** run a **second** dedupe pass at the end of the pipeline (after parsing dates and canonicalising labels). Tracked as `duplicates_after_normalisation`.

### Empty free text becomes "100% left feedback"
**Symptom:** the dashboard reports `feedback_with_text_pct = 100` when the real value is 44.78%.

**Cause:** CSV cannot distinguish `""` from a missing value, so `pd.read_csv` turns every empty cell back into `NaN`. Then `data["open_feedback"].astype(str)` yields the literal string `"nan"`, which is not `""` — so every row counts as having feedback.

**Fix:** one loader (`analysis.load_clean_data`) re-asserts `""` after reading, and the emptiness check is casefolded against a token set that includes `nan`, `<na>` and `null`.

### `AttributeError: 'float' object has no attribute 'title'`
**Symptom:** while injecting case noise, on `value.title()`.

**Cause:** the casing step ran *after* blank answers had been set to `NaN`, so it received floats.

**Fix:** mask out `NaN` before styling, and only inject casing into non-null cells.

---

## 3. Pandas 3.x / NumPy 2.x specifics

| Symptom | Cause / fix |
| --- | --- |
| `ValueError: 'x' is not in the subpath of 'y'` in chart logging | `path.relative_to()` was called on a path outside the project (tests use a temp dir). Fix: wrap in `try/except ValueError` and log the absolute path. |
| String columns load as `str` instead of `object` | Pandas 3.0 infers string dtypes. Code that assumed `object` breaks. Fix: operate on `astype("string")` before `.str` accessors. |
| `pd.to_datetime(...)` returns `datetime64[us]` not `[ns]` | pandas 3.0 default unit changed. Comparison with `datetime64[ns]` still works; don't assert on the dtype string. |
| `SettingWithCopyWarning` after filtering | You're assigning into a slice. Fix: `df = df.loc[mask].copy()` before adding columns. |
| `.applymap` missing | Removed in pandas 1.0 — use `df.map(...)` (DataFrame) or `series.apply(...)`. |

---

## 4. Streamlit

### `StreamlitDuplicateElementId: multiple plotly_chart elements with the same auto-generated ID`
**Symptom:** the dashboard renders, then crashes when two tabs are visited.

**Cause:** the same figure object (same type + same parameters) rendered in two places gets the same auto-generated element ID.

**Fix:** pass a unique `key=` to every `st.plotly_chart`, `st.dataframe`, etc. Caught automatically by `tests/test_dashboard.py`.

### `use_container_width` deprecation warning
Streamlit is replacing `use_container_width=True` with `width="stretch"`. The project uses a small helper so it works on both APIs:
```python
def stretch_kwargs():
    return {"width": "stretch"} if "width" in inspect.signature(st.plotly_chart).parameters \
        else {"use_container_width": True}
```

### Widget changes don't re-run anything
Every widget re-runs the script automatically. If a *computed* value looks stale, it's caching: `@st.cache_data` keys on function arguments, so pass the dataset fingerprint (this project does, via `fingerprint(filtered)`) or call `st.cache_data.clear()` after regenerating data.

### `FileNotFoundError` for the dataset on a fresh clone
`load_clean_dataset()` generates and cleans the data if the CSV is missing — so `streamlit run dashboard.py` works on a fresh clone with no pre-step.

### The dashboard shows no charts, only grey boxes
Plotly is still rendering (or the browser is throttled). Wait a few seconds. If it persists, check that `kaleido` isn't required for on-screen rendering — it is only needed for static image export.

---

## 5. Tests

### `python tests/test_pipeline.py` says `NameError: name 'pd' is not defined`
The test file needs its own `import pandas as pd` — tests import from `src`, but each module must import what it uses.

### Tests pass but the charts in `outputs/` are from a 200-respondent run
Tests build fixtures **in memory** and redirect `config.CHARTS_DIR` to a temp directory so they never touch the real outputs. If you see different numbers, regenerate:
```bash
python main.py all
```

---

## 6. Streaming / screenshots (optional)

If you want to screenshot the dashboard, the cached Playwright Chromium in `%LOCALAPPDATA%\ms-playwright` can be used directly:

```python
browser = p.chromium.launch(executable_path=r"...\ms-playwright\chromium-1243\chrome-win64\chrome.exe")
```
Points of failure: the server must actually be listening (`wait_for_server`), and Plotly must have drawn its SVG — wait for `.js-plotly-plot svg`, not just `.js-plotly-plot`, or you'll capture the empty grey placeholders.
