# GitHub Upload Guide

**Author:** Harsha K S

Everything needed to take this project from your laptop to a public repo that looks intentional in a recruiter's 30-second glance.

---

## 1. Repo naming and description

| Field | Value |
| --- | --- |
| **Repo name** | `Poll-Results-Visualize` |
| **Owner** | [`harshaks17-ai`](https://github.com/harshaks17-ai) |
| **Description** | `End-to-end poll/survey analysis pipeline — cleaning, statistics, charts and an interactive Streamlit dashboard (Python, Pandas, Plotly).` |
| **Visibility** | Public (it's portfolio work; the data is synthetic) |
| **Topics** | `python` `pandas` `data-analysis` `data-visualization` `plotly` `streamlit` `matplotlib` `seaborn` `survey-analysis` `dashboard` `eda` `data-science` |

Avoid: `poll-project`, `my-project`, `poll123`, `New folder`.

---

## 2. Before you push — the checklist

```bash
# 1. Nothing secret, nothing local
git status --short

# 2. The pipeline actually runs from a clean clone
python main.py all

# 3. Tests pass
python tests/test_pipeline.py

# 4. .gitignore is in place BEFORE the first commit
cat .gitignore
```

The `.gitignore` in this project already excludes `__pycache__/`, `.venv/`, `venv/`, `.env`, `*.pyc`, `.ipynb_checkpoints/`, `.DS_Store` and the IDE folders.

**Decide once: do you commit `outputs/` or not?**

Committing the generated charts is what makes the repo convincing — the README images render immediately, no setup needed. This project therefore commits `outputs/charts/` and `outputs/reports/` (they're regenerable, but they're also the proof). Keep `data/` committed too: both CSVs are small text files and the raw file is the "before" half of the story.

---

## 3. First commit

```bash
cd Poll-Results-Visualize

git init
git add .
git commit -m "feat: poll results visualizer with cleaning, charts and streamlit dashboard"
git branch -M main
```

Suggested commit message if you prefer conventional commits:

```text
feat: add poll results visualizer pipeline

- synthetic poll generator with demographic tilts and injected dirt
- cleaning pipeline (dedupe x2, casing, junk answers, mixed date parsing)
- analysis (share %, MoE, breakdowns, trend, word frequencies)
- 10 matplotlib charts + interactive Plotly Streamlit dashboard
- insight report, data-quality report, JSON summary
- 15 pipeline tests + 2 headless dashboard tests + a 17-check browser test
```

---

## 4. Connect and push

```bash
git remote add origin https://github.com/harshaks17-ai/Poll-Results-Visualize.git
git push -u origin main
```

Or with the GitHub CLI (no manual repo creation):

```bash
gh repo create Poll-Results-Visualize --public --source=. --remote=origin --push
gh repo edit --add-topic python,pandas,data-analysis,data-visualization,plotly,streamlit,eda,dashboard
gh repo edit --description "End-to-end poll/survey analysis pipeline - cleaning, statistics, charts and an interactive Streamlit dashboard (Python, Pandas, Plotly)."
```

> If the repo was created on GitHub with an initial commit (a README from the template), use `git pull --rebase origin main` before your first push.

---

## 5. Commit hygiene that recruiters notice

Good history looks like a project being *built*, not one that appeared:

```bash
git add src/data_generator.py src/config.py
git commit -m "feat: synthetic poll generator with regional and age-group tilts"

git add src/data_cleaning.py
git commit -m "feat: cleaning pipeline with second dedupe pass after normalisation"

git add src/analysis.py
git commit -m "feat: share, margin-of-error and demographic breakdown analysis"

git add src/visualization.py
git commit -m "feat: 10 matplotlib charts including dependency-free word cloud"

git add dashboard.py
git commit -m "feat: streamlit dashboard with light theme and interactive plotly charts"

git add tests/
git commit -m "test: add pipeline tests and headless dashboard smoke test"

git add README.md docs/ images/
git commit -m "docs: README, interview prep, GitHub guide and troubleshooting"
```

Also worth doing:

- **`git log --oneline`** — readable history is part of the deliverable.
- **One logical change per commit** — never "final final v2".
- **Never commit `.venv/`, `__pycache__/`, `.env`, or huge CSV dumps** of real personal data.

---

## 6. README-first presentation order

What a recruiter sees, in order: repo name → description → README top. This README is ordered for exactly that:

1. Title + one-sentence value proposition + tech stack badges
2. Feature table
3. Problem → Solution with an architecture diagram
4. Quick start (copy-paste commands)
5. **Results with real numbers** — the proof it runs
6. Screenshots (charts + dashboard)
7. Testing section
8. Links to the docs

If you screenshot anything for a portfolio, capture the **dashboard** first — it's the most impressive artefact and it takes one command:

```bash
python main.py dashboard
```

---

## 7. Screenshots to capture (and where they go in the README)

| Artefact | Command | README location |
| --- | --- | --- |
| Raw dataset preview | open `data/raw/poll_responses_raw.csv` | Screenshots section |
| Cleaned dataset preview | open `data/processed/poll_responses_clean.csv` | Screenshots section |
| Console headline numbers | `python main.py all` | Results section |
| 10 charts | `outputs/charts/` | Screenshots grid |
| Dashboard tabs ×5 | `python main.py dashboard` | Dashboard walkthrough |
| GitHub repo page | browser | Proof section of your portfolio / LinkedIn |

Copy the chart PNGs into `images/` so the README renders on GitHub regardless of where the repo is cloned:

```bash
cp outputs/charts/*.png images/    # Windows: Copy-Item "outputs\charts\*.png" images\
```

---

## 8. Post-push polish

- **Pin the repo** on your GitHub profile.
- **Enable "About" description + topics** (see step 4).
- **Add a `LICENSE`** — MIT is already included.
- **LinkedIn post**: one screenshot of the dashboard, one sentence on what problem it solves, the repo link. Not "I built a project" — "here's what I made and why".
- **Star your own repo** and open one realistic issue to yourself (e.g. "add chi-square significance testing between regions") — open issues with a clear scope read as active ownership.

---

## 9. If something goes wrong

| Problem | Fix |
| --- | --- |
| `fatal: remote origin already exists` | `git remote set-url origin https://github.com/<user>/<repo>.git` |
| `! [rejected] main -> main (fetch first)` | `git pull --rebase origin main` then push |
| `fatal: not a git repository` | run `git init` from the project root |
| Pushed `.venv/` | `git rm -r --cached .venv` `echo ".venv/" >> .gitignore` `git commit -m "chore: ignore virtualenv"` |
| Windows line endings everywhere | `git config --global core.autocrlf true` |
| README images not showing | image paths are case-sensitive on GitHub — keep the `images/` folder with the exact names used |
