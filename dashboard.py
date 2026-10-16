"""
Poll Results Visualizer - interactive Streamlit dashboard.

Run from the project root:
    python main.py dashboard
    # or
    streamlit run dashboard.py

Design notes:
* light, high-contrast theme built from scratch with CSS (no default Streamlit skin)
* every accent colour is used consistently across KPI tiles, tabs and plotly charts
* works with the bundled synthetic dataset *or* any uploaded poll CSV
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # allow `streamlit run dashboard.py`

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from src import analysis, config, data_cleaning, data_generator, insights


def stretch_kwargs() -> dict:
    """Return the kwargs that make an element fill its container.

    Recent Streamlit versions accept `width="stretch"`; older ones only know
    `**stretch_kwargs()`. Detect once and stay compatible with both.
    """
    return {"width": "stretch"} if "width" in inspect.signature(st.plotly_chart).parameters \
        else {"use_container_width": True}

# --------------------------------------------------------------------------- #
# Page configuration (must be the first Streamlit call)
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Poll Results Visualizer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------- #
# Design tokens
# --------------------------------------------------------------------------- #
PALETTE = config.CHART_PALETTE
INK = config.THEME["text"]
MUTED = config.THEME["muted"]
BORDER = config.THEME["border"]

PLOT_LAYOUT = dict(
    template="plotly_white",
    colorway=PALETTE,
    font=dict(family="Segoe UI, system-ui, sans-serif", size=13, color=INK),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=10, r=10, t=46, b=10),
    hoverlabel=dict(bgcolor="white", font_size=12, bordercolor=BORDER),
    legend=dict(orientation="h", yanchor="bottom", y=-0.28, xanchor="center", x=0.5),
)

CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  html, body, [class*="css"] { font-family: 'Inter', 'Segoe UI', system-ui, sans-serif; }

  .stApp {
    background:
      radial-gradient(1100px 520px at 8% -10%, rgba(79,70,229,.10), transparent 60%),
      radial-gradient(900px 480px at 100% 0%, rgba(14,165,233,.12), transparent 55%),
      linear-gradient(180deg, #F7F9FD 0%, #F2F6FC 100%);
  }

  /* ---------- hero ---------- */
  .hero {
    background: linear-gradient(120deg, #4F46E5 0%, #4F46E5 42%, #0EA5E9 100%);
    border-radius: 20px;
    padding: 26px 30px 24px 30px;
    color: #FFFFFF;
    box-shadow: 0 14px 34px rgba(79,70,229,.26);
    position: relative;
    overflow: hidden;
  }
  .hero::after {
    content: "";
    position: absolute; right: -60px; top: -80px;
    width: 260px; height: 260px; border-radius: 50%;
    background: rgba(255,255,255,.12);
  }
  .hero::before {
    content: "";
    position: absolute; right: 90px; bottom: -110px;
    width: 200px; height: 200px; border-radius: 50%;
    background: rgba(255,255,255,.08);
  }
  .hero h1 { margin: 0; font-size: 30px; font-weight: 800; letter-spacing: -.5px; color: #fff; }
  .hero p  { margin: 6px 0 0 0; font-size: 14.5px; color: rgba(255,255,255,.88); max-width: 760px; }
  .hero .pills { margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap; }
  .hero .pill {
    background: rgba(255,255,255,.16);
    border: 1px solid rgba(255,255,255,.34);
    color: #fff; border-radius: 999px; padding: 3px 12px;
    font-size: 12px; font-weight: 600; letter-spacing: .2px;
  }

  /* ---------- KPI tiles ---------- */
  .kpi {
    background: #FFFFFF;
    border: 1px solid #E4EAF3;
    border-radius: 16px;
    padding: 16px 18px 14px 18px;
    box-shadow: 0 4px 14px rgba(15,23,42,.05);
    border-left: 4px solid var(--accent, #4F46E5);
    height: 100%;
  }
  .kpi .label {
    font-size: 11.5px; font-weight: 700; text-transform: uppercase;
    letter-spacing: .7px; color: #64748B; margin-bottom: 6px;
  }
  .kpi .value { font-size: 27px; font-weight: 800; color: #1E293B; line-height: 1.1; }
  .kpi .delta { font-size: 12px; color: #64748B; margin-top: 5px; }
  .kpi .delta b { color: var(--accent, #4F46E5); font-weight: 700; }

  /* ---------- section + cards ---------- */
  .section-title {
    font-size: 19px; font-weight: 800; color: #1E293B;
    margin: 6px 0 2px 0; letter-spacing: -.3px;
  }
  .section-sub { font-size: 13px; color: #64748B; margin-bottom: 14px; }

  .card {
    background: #FFFFFF;
    border: 1px solid #E4EAF3;
    border-radius: 16px;
    padding: 18px 20px;
    box-shadow: 0 4px 14px rgba(15,23,42,.05);
    height: 100%;
  }
  .card h4 {
    margin: 0 0 10px 0; font-size: 14.5px; font-weight: 700; color: #1E293B;
  }
  .card .body { font-size: 13.2px; color: #475569; line-height: 1.62; }

  .insight {
    background: #FFFFFF;
    border: 1px solid #E4EAF3;
    border-left: 4px solid #10B981;
    border-radius: 14px;
    padding: 14px 18px;
    font-size: 13.4px; color: #334155; line-height: 1.6;
    box-shadow: 0 3px 10px rgba(15,23,42,.04);
  }
  .insight b { color: #1E293B; }
  .insight.amber { border-left-color: #F59E0B; }
  .insight.indigo { border-left-color: #4F46E5; }
  .insight.sky { border-left-color: #0EA5E9; }
  .insight.rose { border-left-color: #EC4899; }

  /* ---------- tabs ---------- */
  button[data-baseweb="tab"] {
    font-weight: 600; font-size: 13.5px; color: #64748B;
    padding: 9px 16px; border-radius: 10px 10px 0 0;
  }
  button[data-baseweb="tab"][aria-selected="true"] {
    color: #4F46E5; background: #FFFFFF;
  }
  div[data-baseweb="tab-highlight"] { background-color: #4F46E5 !important; }
  div[data-baseweb="tab-border"] { display: none; }

  /* ---------- sidebar ---------- */
  section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FFFFFF 0%, #F7F9FD 100%);
    border-right: 1px solid #E4EAF3;
  }
  section[data-testid="stSidebar"] h3 { font-weight: 800; color: #1E293B; font-size: 15px; }

  /* ---------- misc ---------- */
  .stDownloadButton button {
    background: linear-gradient(120deg, #4F46E5, #0EA5E9) !important;
    color: #fff !important; border: none !important; font-weight: 600 !important;
    border-radius: 10px !important;
  }
  .stExpander { border-radius: 12px; border: 1px solid #E4EAF3; background: #fff; }
  #MainMenu, footer { visibility: hidden; }
  hr { border: none; border-top: 1px solid #E4EAF3; margin: 14px 0; }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def load_clean_dataset() -> pd.DataFrame:
    """Load the cleaned dataset, running the pipeline first if it is missing."""
    if not config.CLEAN_CSV_PATH.exists():
        data_generator.generate_and_save()
        data_cleaning.run_cleaning()
    return analysis.load_clean_data()


@st.cache_data(show_spinner=False)
def load_analysis(frame_hash: str) -> dict:
    """Run (and cache) the analysis bundle keyed on the dataset fingerprint."""
    return analysis.full_analysis(analysis.load_clean_data())


def fingerprint(frame: pd.DataFrame) -> str:
    """Stable-ish fingerprint used to invalidate the cached analysis bundle."""
    return f"{len(frame)}-{frame['respondent_id'].nunique()}-{frame['response_date'].max()}"


@st.cache_data(show_spinner=False)
def read_uploaded(uploaded) -> tuple[pd.DataFrame | None, str | None]:
    """Validate + clean an uploaded poll CSV export."""
    try:
        raw = pd.read_csv(uploaded)
    except Exception as exc:  # pragma: no cover - surfaced in the UI
        return None, f"Could not read the file: {exc}"

    required = {"respondent_id", "response_date", "question_id", "option_selected"}
    missing = required - set(str(col).strip().lower() for col in raw.columns)
    if missing:
        return None, (
            "The file is missing required columns: "
            + ", ".join(sorted(missing))
            + ".\n\nExpected a Google-Forms style export with respondent_id, "
            "response_date, question_id, option_selected (plus optional region, "
            "age_group, gender, device, channel, open_feedback)."
        )
    clean, _ = data_cleaning.clean_poll_data(raw)
    return clean, None


# --------------------------------------------------------------------------- #
# Reusable components
# --------------------------------------------------------------------------- #
def kpi_tile(label: str, value: str, delta: str, accent: str) -> None:
    st.markdown(
        f"""<div class="kpi" style="--accent:{accent}">
              <div class="label">{label}</div>
              <div class="value">{value}</div>
              <div class="delta">{delta}</div>
            </div>""",
        unsafe_allow_html=True,
    )


def card(title: str, body: str) -> None:
    st.markdown(
        f'<div class="card"><h4>{title}</h4><div class="body">{body}</div></div>',
        unsafe_allow_html=True,
    )


def insight(text: str, tone: str = "emerald") -> None:
    st.markdown(f'<div class="insight {tone}">{text}</div>', unsafe_allow_html=True)


def styled(fig, height: int | None = None) -> go.Figure:
    fig.update_layout(**PLOT_LAYOUT)
    if height:
        fig.update_layout(height=height)
    fig.update_xaxes(showgrid=False, linecolor=BORDER)
    fig.update_yaxes(gridcolor="#EEF2F8", linecolor=BORDER)
    return fig


def hero() -> None:
    st.markdown(
        """
        <div class="hero">
          <h1>📊 Poll Results Visualizer</h1>
          <p>Clean raw survey exports, quantify who is leading and by how much,
             break the results down by region and demographics, and turn free-text
             feedback into decisions — all in one dashboard.</p>
          <div class="pills">
            <span class="pill">Pandas ETL</span>
            <span class="pill">Plotly + Matplotlib</span>
            <span class="pill">Streamlit</span>
            <span class="pill">Synthetic dataset (1,200 respondents)</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #
def chart_option_share(data: pd.DataFrame, question_id: str) -> go.Figure:
    table = analysis.option_share_table(data, question_id).sort_values("share_pct")
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(table) - 1, -1, -1)]
    fig = go.Figure(
        go.Bar(
            x=table["share_pct"],
            y=table["option_selected"],
            orientation="h",
            marker=dict(color=colors),
            text=[f"{v:.1f}%  ({int(c):,})" for v, c in zip(table["share_pct"], table["votes"])],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>Share: %{x:.2f}%<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"{question_id} — {data.loc[data['question_id'] == question_id, 'question'].iloc[0]}",
        xaxis_title="Share of valid responses (%)",
        yaxis_title="",
    )
    return styled(fig, 420)


def chart_donut(data: pd.DataFrame, question_id: str) -> go.Figure:
    summary = analysis.question_summary(data, question_id)
    table = analysis.option_share_table(data, question_id)
    fig = go.Figure(
        go.Pie(
            labels=table["option_selected"],
            values=table["share_pct"],
            hole=0.58,
            marker=dict(colors=[PALETTE[i % len(PALETTE)] for i in range(len(table))]),
            textinfo="percent",
            textfont=dict(size=13, color="white"),
            hovertemplate="<b>%{label}</b><br>Share: %{value:.2f}%<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"Headline split — {question_id}",
        annotations=[
            dict(
                text=f"<b>{summary['leading_option'].split(' - ')[0]}</b><br>"
                f"{summary['leading_share_pct']:.1f}%",
                x=0.5, y=0.5, showarrow=False, font=dict(size=15, color=PALETTE[0]),
            )
        ],
    )
    fig.update_layout(**PLOT_LAYOUT)
    fig.update_layout(legend=dict(orientation="v", y=0.5, x=1.02), height=430)
    return fig


def chart_region_stacked(data: pd.DataFrame, question_id: str) -> go.Figure:
    wide = analysis.crosstab_share(data, question_id, "region")
    fig = go.Figure()
    for i, option in enumerate(wide.columns):
        fig.add_trace(
            go.Bar(
                x=wide.index.astype(str),
                y=wide[option],
                name=option,
                marker=dict(color=PALETTE[i % len(PALETTE)]),
                text=[f"{v:.0f}%" if v >= 5 else "" for v in wide[option]],
                textposition="inside",
                textfont=dict(color="white", size=12),
                hovertemplate=f"<b>{option}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="stack",
        title=f"Option composition inside each region — {question_id}",
        yaxis_title="Share within region (%)",
        xaxis_title="Region",
    )
    return styled(fig, 470)


def chart_demographic(data: pd.DataFrame, question_id: str, dimension: str) -> go.Figure:
    long = analysis.breakdown_table(data, question_id, dimension)
    options = analysis.option_share_table(data, question_id)["option_selected"].tolist()
    fig = go.Figure()
    for i, group in enumerate(sorted(long[dimension].unique().tolist())):
        shares = [
            float(
                long.loc[
                    (long[dimension] == group) & (long["option_selected"] == option),
                    "share_pct",
                ].sum()
            )
            for option in options
        ]
        fig.add_trace(
            go.Bar(
                x=options,
                y=shares,
                name=str(group),
                marker=dict(color=PALETTE[i % len(PALETTE)]),
                hovertemplate=f"<b>{group}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="group",
        title=f"{question_id} by {dimension.replace('_', ' ')} (share within each group)",
        yaxis_title="Share within group (%)",
    )
    return styled(fig, 470)


def chart_heatmap(data: pd.DataFrame, question_id: str) -> go.Figure:
    wide = analysis.crosstab_share(data, question_id, "region")
    fig = px.imshow(
        wide,
        text_auto=".1f",
        color_continuous_scale=["#FFFFFF", "#C7D2FE", "#6366F1", "#4F46E5"],
        aspect="auto",
        labels=dict(color="Share (%)"),
    )
    fig.update_layout(
        title=f"Heatmap — option share by region ({question_id})",
        xaxis_title="Option selected",
        yaxis_title="Region",
    )
    return styled(fig, 460)


def chart_trend(trend: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=trend["date"],
            y=trend["responses"],
            mode="lines+markers",
            name="Daily responses",
            line=dict(color=PALETTE[1], width=1.8),
            marker=dict(size=4.5, color=PALETTE[1]),
            fill="tozeroy",
            fillcolor="rgba(14,165,233,.13)",
            hovertemplate="<b>%{x|%d %b %Y}</b><br>%{y} responses<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend["date"],
            y=trend["rolling_7d"],
            mode="lines",
            name="7-day rolling average",
            line=dict(color=PALETTE[0], width=3),
            hovertemplate="<b>%{x|%d %b %Y}</b><br>7d avg: %{y:.1f}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Response volume across the polling window",
        yaxis_title="Responses",
        xaxis_title="Date",
    )
    return styled(fig, 440)


def chart_words(words: pd.DataFrame) -> go.Figure:
    """Interactive word cloud: a golden-angle sunflower layout, no extra deps."""
    top = words.head(40).reset_index(drop=True)
    if top.empty:
        fig = go.Figure()
        fig.update_layout(title="No free-text responses in this export")
        return styled(fig, 400)

    max_freq = float(top["frequency"].max())
    golden = np.pi * (3 - np.sqrt(5))
    radius = np.sqrt(np.arange(len(top)) + 0.6) * 9.2
    angle = np.arange(len(top)) * golden
    fig = go.Figure(
        go.Scatter(
            x=radius * np.cos(angle),
            y=radius * np.sin(angle) * 0.62,
            mode="text",
            text=top["word"],
            textfont=dict(
                size=[11 + 30 * np.sqrt(f / max_freq) for f in top["frequency"]],
                color=[PALETTE[i % len(PALETTE)] for i in range(len(top))],
            ),
            hovertemplate="<b>%{text}</b><br>%{customdata} mentions<extra></extra>",
            customdata=top["frequency"],
        )
    )
    limit = np.sqrt(len(top)) * 9.2
    fig.update_layout(
        title="Word cloud — most repeated themes in the free-text feedback",
        xaxis=dict(visible=False, range=[-limit * 1.1, limit * 1.1]),
        yaxis=dict(visible=False, range=[-limit * 0.75, limit * 0.75]),
    )
    fig.update_layout(**PLOT_LAYOUT)
    fig.update_layout(height=470)
    return fig


def chart_satisfaction(data: pd.DataFrame, question_id: str = "Q3") -> go.Figure:
    table = analysis.option_share_table(data, question_id)
    scores = pd.to_numeric(
        table["option_selected"].str.extract(r"^(\d)", expand=False), errors="coerce"
    )
    table = table.assign(score=scores).sort_values("score")
    colors = [
        "#EF4444" if s <= 2 else "#F59E0B" if s == 3 else "#10B981" for s in table["score"]
    ]
    fig = go.Figure(
        go.Bar(
            x=table["option_selected"],
            y=table["share_pct"],
            marker=dict(color=colors),
            text=[f"{v:.1f}%" for v in table["share_pct"]],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Share: %{y:.2f}%<extra></extra>",
        )
    )
    fig.update_layout(
        title="Satisfaction distribution — red = detractors, amber = passive, green = promoters",
        yaxis_title="Share of responses (%)",
    )
    return styled(fig, 460)


def chart_channels(channels: pd.DataFrame) -> go.Figure:
    """Two clean panels: response volume (left) and satisfaction score (right)."""
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Responses collected", "Average satisfaction (1-5)"),
        horizontal_spacing=0.1,
    )
    fig.add_trace(
        go.Bar(
            x=channels["channel"],
            y=channels["responses"],
            name="Responses",
            marker=dict(color=PALETTE[0]),
            text=channels["responses"],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>%{y:,} responses<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=channels["channel"],
            y=channels["avg_satisfaction"],
            name="Avg satisfaction",
            marker=dict(color=PALETTE[3]),
            text=[f"{v:.2f}" for v in channels["avg_satisfaction"]],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Avg satisfaction: %{y:.2f}/5<extra></extra>",
        ),
        row=1,
        col=2,
    )
    fig.add_hline(
        y=float(channels["avg_satisfaction"].mean()),
        line=dict(color=PALETTE[5], width=2, dash="dash"),
        annotation_text=f"Average {channels['avg_satisfaction'].mean():.2f}",
        annotation_position="top right",
        row=1,
        col=2,
    )
    fig.update_yaxes(range=[0, channels["responses"].max() * 1.22], row=1, col=1)
    fig.update_yaxes(range=[0, 5.6], row=1, col=2)
    fig.update_layout(title="Channel performance — volume vs. satisfaction")
    return styled(fig, 460)


def chart_correlation(data: pd.DataFrame, question_id: str = "Q1") -> go.Figure:
    """Diverging bar: region vs. the national average for the leading option."""
    wide = analysis.crosstab_share(data, question_id, "region")
    leading = wide.mean(axis=0).idxmax()
    national = float(wide[leading].mean())
    table = wide[leading].sort_values(ascending=False)
    delta = table - national
    fig = go.Figure(
        go.Bar(
            x=delta.index.astype(str),
            y=delta,
            marker=dict(
                color=["#10B981" if v >= 0 else "#EF4444" for v in delta]
            ),
            text=[f"{v:+.1f} pts" for v in delta],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>National avg: "
            + f"{national:.1f}%<br>Difference: %{{y:+.1f}} pts<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"Where “{leading.split(' - ')[0]}” is over / under-performing vs. "
        f"the {national:.1f}% national average",
        yaxis_title="Difference from national average (percentage points)",
        xaxis_title="Region",
    )
    return styled(fig, 440)


# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
def tab_overview(data: pd.DataFrame, bundle: dict, question_id: str) -> None:
    summary = analysis.question_summary(data, question_id)
    c1, c2 = st.columns([1.05, 1])
    with c1:
        st.plotly_chart(chart_option_share(data, question_id), **stretch_kwargs(), key="chart_option_share")
    with c2:
        st.plotly_chart(chart_donut(data, question_id), **stretch_kwargs(), key="chart_donut")

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    insight(
        f"<b>{summary['leading_option']}</b> leads with "
        f"<b>{summary['leading_share_pct']:.1f}%</b> of "
        f"{summary['total_responses']:,} valid responses "
        f"(±{summary['margin_of_error_95']} pts at 95% confidence), ahead of "
        f"{summary['runner_up_option']} on {summary['runner_up_share_pct']:.1f}%. "
        f"The lead is <b>{summary['lead_margin_pct']:.1f} points</b>",
        "indigo",
    )
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    rows = bundle["tables"]["option_share"]
    rows = rows.loc[rows["question_id"] == question_id]
    st.markdown('<div class="card"><h4>Full results table</h4>', unsafe_allow_html=True)
    display = rows[["rank", "option_selected", "votes", "share_pct"]].rename(
        columns={
            "rank": "#",
            "option_selected": "Option",
            "votes": "Votes",
            "share_pct": "Share (%)",
        }
    ).reset_index(drop=True)
    st.dataframe(display, **stretch_kwargs(), hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


def tab_regions(data: pd.DataFrame, question_id: str) -> None:
    st.plotly_chart(chart_region_stacked(data, question_id), **stretch_kwargs(), key="chart_region_stacked")
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        st.plotly_chart(chart_heatmap(data, question_id), **stretch_kwargs(), key="chart_heatmap")
    with right:
        st.plotly_chart(chart_correlation(data, question_id), **stretch_kwargs(), key="chart_correlation")

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    wide = analysis.crosstab_share(data, question_id, "region")
    leading = wide.mean(axis=0).idxmax()
    strongest = wide[leading].idxmax()
    weakest = wide[leading].idxmin()
    swing = float(wide[leading].max() - wide[leading].min())
    insight(
        f"<b>{leading}</b> is strongest in <b>{strongest}</b> "
        f"({wide[leading].max():.1f}%) and weakest in <b>{weakest}</b> "
        f"({wide[leading].min():.1f}%) — a swing of <b>{swing:.1f} points</b>. "
        f"A single national headline would hide this, so local strategy must differ by region.",
        "emerald",
    )
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="card"><h4>Region × option — share within region (%)</h4>', unsafe_allow_html=True)
    st.dataframe(wide.style.format("{:.1f}%").background_gradient(cmap="Blues", axis=None), **stretch_kwargs())
    st.markdown("</div>", unsafe_allow_html=True)


def tab_demographics(data: pd.DataFrame, question_id: str) -> None:
    dimension = st.radio(
        "Break down by",
        ["Age group", "Gender", "Device", "Channel"],
        horizontal=True,
        label_visibility="collapsed",
    )
    mapping = {"Age group": "age_group", "Gender": "gender", "Device": "device", "Channel": "channel"}
    dim = mapping[dimension]
    st.plotly_chart(chart_demographic(data, question_id, dim), **stretch_kwargs(), key="chart_demographic")
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    st.plotly_chart(chart_satisfaction(data, "Q3"), **stretch_kwargs(), key="chart_satisfaction")
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    st.plotly_chart(chart_channels(bundle_channels(data)), **stretch_kwargs(), key="chart_channels")

    summary = analysis.question_summary(data, "Q3")
    insight(
        f"Service satisfaction averages <b>{summary['mean_score']}/5</b>. "
        f"Promoters (4–5) make up <b>{summary['promoters_pct']:.1f}%</b> versus "
        f"<b>{summary['detractors_pct']:.1f}%</b> detractors, giving a net score of "
        f"<b>{summary['net_promoter_score']:+.1f} points</b>.",
        "amber",
    )


@st.cache_data(show_spinner=False)
def bundle_channels(data: pd.DataFrame) -> pd.DataFrame:
    return analysis.channel_performance(data)


def tab_trend(data: pd.DataFrame, bundle: dict) -> None:
    st.plotly_chart(chart_trend(bundle["trend"]), **stretch_kwargs(), key="chart_trend")
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    left, right = st.columns([1, 1.5])
    with left:
        st.plotly_chart(chart_demographic(data, "Q1", "age_group"), **stretch_kwargs(), key="chart_trend_demographic")
    with right:
        st.markdown('<div class="card"><h4>Daily volume table</h4>', unsafe_allow_html=True)
        trend = bundle["trend"].copy()
        trend["date"] = trend["date"].dt.strftime("%d %b %Y")
        trend = trend.rename(
            columns={
                "date": "Date",
                "responses": "Responses",
                "rolling_7d": "7-day avg",
                "pct_of_total": "Share (%)",
            }
        )
        st.dataframe(trend, **stretch_kwargs(), hide_index=True, height=380)
        st.markdown("</div>", unsafe_allow_html=True)

    peak = bundle["trend"].loc[bundle["trend"]["responses"].idxmax()]
    insight(
        f"Collection peaked on <b>{peak['date']:%d %b %Y}</b> with "
        f"<b>{int(peak['responses'])}</b> responses. Mid-poll promotion lifts the "
        f"7-day rolling average, so the trend chart is the fastest way to prove that "
        f"campaign effort actually moved the response rate.",
        "sky",
    )


def tab_text(data: pd.DataFrame, bundle: dict) -> None:
    st.plotly_chart(chart_words(bundle["words"]), **stretch_kwargs(), key="chart_words")
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    left, right = st.columns([1, 1.6])
    with left:
        st.markdown('<div class="card"><h4>Top words</h4>', unsafe_allow_html=True)
        words = bundle["words"].head(15).rename(columns={"word": "Word", "frequency": "Mentions"})
        st.dataframe(words, **stretch_kwargs(), hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        top = ", ".join(
            f"<b>{row['word']}</b> ({int(row['frequency'])})"
            for _, row in bundle["words"].head(8).iterrows()
        )
        insight(
            f"Recurring themes: {top}. Grouping these clusters into praise vs. complaints "
            f"gives the product team a prioritised backlog straight from raw feedback — "
            f"no manual reading required.",
            "rose",
        )
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown(
            '<div class="card"><h4>Raw free-text responses</h4>', unsafe_allow_html=True
        )
        feedback = data.loc[
            data["open_feedback"].astype(str).str.strip() != "",
            ["respondent_id", "region", "age_group", "open_feedback"],
        ].head(25)
        st.dataframe(
            feedback.rename(columns={"open_feedback": "Feedback"}),
            **stretch_kwargs(),
            hide_index=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)


def tab_data(data: pd.DataFrame, bundle: dict) -> None:
    overall = bundle["overall"]
    insight(
        f"The raw export contained junk rows: duplicates, blank answers, mixed casing, "
        f"stray whitespace and three date formats. Cleaning reduced "
        f"<b>{overall['responses']:,}</b> usable responses from the raw file while keeping "
        f"every row traceable to a respondent and a question.",
        "indigo",
    )
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="card"><h4>Cleaned dataset (first 200 rows)</h4>', unsafe_allow_html=True)
    preview = data.head(200).copy()
    preview["response_date"] = preview["response_date"].dt.strftime("%Y-%m-%d")
    st.dataframe(preview, **stretch_kwargs(), hide_index=True, height=420)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    csv = data.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️  Download cleaned dataset (CSV)",
        data=csv,
        file_name="poll_responses_clean.csv",
        mime="text/csv",
    )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    inject_css()
    hero()
    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    # ---------------------------- sidebar ---------------------------------- #
    with st.sidebar:
        st.markdown("### ⚙️ Data source")
        uploaded = st.file_uploader(
            "Upload a poll/survey CSV export",
            type=["csv"],
            help="Columns: respondent_id, response_date, question_id, option_selected (+ optional "
 "region, age_group, gender, device, channel, open_feedback).",
        )

        st.markdown("<hr/>", unsafe_allow_html=True)
        st.markdown("### 🎛️ Filters")

        if uploaded is not None:
            data, error = read_uploaded(uploaded)
            if error:
                st.error(error)
                data = load_clean_dataset()
                st.info("Falling back to the bundled synthetic dataset.")
            else:
                st.success(f"Loaded and cleaned your export ({len(data):,} rows).")
        else:
            data = load_clean_dataset()

        question_ids = sorted(data["question_id"].unique().tolist())
        selected_question = st.selectbox(
            "Question", question_ids, index=0, key="q_select"
        )
        regions = st.multiselect(
            "Region", sorted(data["region"].dropna().unique().tolist()), default=[]
        )
        ages = st.multiselect(
            "Age group", sorted(data["age_group"].dropna().unique().tolist()), default=[]
        )
        genders = st.multiselect(
            "Gender", sorted(data["gender"].dropna().unique().tolist()), default=[]
        )
        devices = st.multiselect(
            "Device", sorted(data["device"].dropna().unique().tolist()), default=[]
        )

        st.markdown("<hr/>", unsafe_allow_html=True)
        if st.button("🔄 Regenerate synthetic dataset", **stretch_kwargs()):
            with st.spinner("Generating a fresh poll dataset..."):
                seed = int(np.random.default_rng().integers(1, 9999))
                config.RANDOM_SEED = seed
                data_generator.generate_and_save()
                data_cleaning.run_cleaning()
                analysis.run_analysis()
                st.cache_data.clear()
            st.success(f"Regenerated with seed {seed}.")
            st.rerun()

        st.markdown("<hr/>", unsafe_allow_html=True)
        st.caption(
            "Built with Streamlit, Plotly, Pandas & Matplotlib. "
            "Dataset is synthetic and generated locally."
        )

    # --------------------------- filtering --------------------------------- #
    filtered = data.copy()
    if regions:
        filtered = filtered.loc[filtered["region"].isin(regions)]
    if ages:
        filtered = filtered.loc[filtered["age_group"].isin(ages)]
    if genders:
        filtered = filtered.loc[filtered["gender"].isin(genders)]
    if devices:
        filtered = filtered.loc[filtered["device"].isin(devices)]

    if filtered.empty:
        st.warning("The current filter combination returns no responses. Widen the filters.")
        return

    bundle = load_analysis(fingerprint(filtered))

    # ----------------------------- KPI row --------------------------------- #
    overall = bundle["overall"]
    lead = analysis.question_summary(filtered, selected_question)
    cols = st.columns(5)
    tiles = [
        ("Valid responses", f"{overall['responses']:,}", f"from {overall['respondents']:,} unique respondents", PALETTE[0]),
        ("Questions asked", f"{overall['questions']}", f"{overall['regions']} regions covered", PALETTE[1]),
        ("Polling window", f"{overall['date_from'][5:]} → {overall['date_to'][5:]}", f"{overall['date_from'][:4]} (30 days)", PALETTE[2]),
        ("Avg satisfaction", f"{overall['avg_satisfaction']}/5", f"{overall['feedback_with_text_pct']:.0f}% left written feedback", PALETTE[3]),
        (
            f"Leader · {selected_question}",
            f"{lead['leading_share_pct']:.1f}%",
            f"±{lead['margin_of_error_95']} pts MoE · lead {lead['lead_margin_pct']:.1f} pts",
            PALETTE[4],
        ),
    ]
    for col, (label, value, delta, accent) in zip(cols, tiles):
        with col:
            kpi_tile(label, value, delta, accent)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ------------------------------ tabs ----------------------------------- #
    tabs = st.tabs(
        ["📈 Overview", "🗺️ Regions", "👥 Demographics", "📅 Trend", "💬 Text insights", "🗃️ Data"]
    )
    with tabs[0]:
        tab_overview(filtered, bundle, selected_question)
    with tabs[1]:
        tab_regions(filtered, selected_question)
    with tabs[2]:
        tab_demographics(filtered, selected_question)
    with tabs[3]:
        tab_trend(filtered, bundle)
    with tabs[4]:
        tab_text(filtered, bundle)
    with tabs[5]:
        tab_data(filtered, bundle)

    st.markdown("<hr/>", unsafe_allow_html=True)
    st.caption(
        "Poll Results Visualizer — synthetic dataset · shares calculated over valid responses "
        "per question · margin of error uses the normal approximation 1.96·√(p(1−p)/n)."
    )


if __name__ == "__main__":
    main()
