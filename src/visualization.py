"""
Visualisation layer: static charts (matplotlib / seaborn) saved to `outputs/charts`.

Design rules:
* light background, no chart-junk, no 3-D, no default rainbow palettes
* every chart states its unit (votes or %) directly on the labels
* the same colour palette is reused everywhere so the dashboard matches
"""

from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap

from . import config
from .analysis import breakdown_table, option_share_table, crosstab_share
from .utils import apply_matplotlib_theme, ensure_directories, get_logger

LOGGER = get_logger()


def _save(fig, filename: str) -> str:
    """Save a figure into outputs/charts and return the relative path."""
    ensure_directories()
    path = config.CHARTS_DIR / filename
    fig.savefig(path, transparent=False)
    plt.close(fig)
    try:
        display_path = path.relative_to(config.PROJECT_ROOT)
    except ValueError:  # output redirected elsewhere (e.g. a temp dir in tests)
        display_path = path
    LOGGER.info("Chart saved -> %s", display_path)
    return str(path)


def _bar_labels(ax, bars, fmt="{:.1f}%", padding=0.15, fontsize=9):
    """Write a value label on top of every bar."""
    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + padding,
            bar.get_y() + bar.get_height() / 2,
            fmt.format(width),
            va="center",
            ha="left",
            fontsize=fontsize,
            color=config.THEME["text"],
            fontweight="medium",
        )


# --------------------------------------------------------------------------- #
# 1. Overall option share (one panel per question)
# --------------------------------------------------------------------------- #
def plot_overall_shares(data: pd.DataFrame) -> str:
    """Horizontal bar chart of option share for every question."""
    apply_matplotlib_theme()
    question_ids = sorted(data["question_id"].unique().tolist())
    n = len(question_ids)
    ncols = 2
    nrows = math.ceil(n / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(13, 4.6 * nrows))
    axes = np.atleast_1d(axes).ravel()

    for ax, qid in zip(axes, question_ids):
        table = option_share_table(data, qid).iloc[::-1]
        colors = [config.CHART_PALETTE[i % len(config.CHART_PALETTE)] for i in range(len(table))]
        bars = ax.barh(table["option_selected"], table["share_pct"], color=colors, height=0.62)
        _bar_labels(ax, bars)
        question_text = data.loc[data["question_id"] == qid, "question"].iloc[0]
        short = f"{question_text[:46]}..." if len(question_text) > 46 else question_text
        ax.set_title(f"{qid}. {short}", loc="left", fontsize=12)
        ax.set_xlabel("Share of responses (%)")
        ax.set_xlim(0, max(100.0, table["share_pct"].max() * 1.18))
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", visible=False)

    for ax in axes[n:]:  # hide unused panels
        ax.axis("off")

    fig.suptitle(
        "Poll Results - Option-wise Share of Responses",
        fontsize=17,
        fontweight="bold",
        color=config.THEME["text"],
        y=0.998,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    return _save(fig, "01_overall_option_share.png")


# --------------------------------------------------------------------------- #
# 2. Donut chart for the headline question
# --------------------------------------------------------------------------- #
def plot_donut(data: pd.DataFrame, question_id: str = "Q1") -> str:
    """Donut chart highlighting the leading option."""
    apply_matplotlib_theme()
    table = option_share_table(data, question_id)
    labels = table["option_selected"].tolist()
    values = table["share_pct"].to_numpy()
    colors = [config.CHART_PALETTE[i % len(config.CHART_PALETTE)] for i in range(len(table))]

    fig, ax = plt.subplots(figsize=(8.5, 7))
    wedges, _ = ax.pie(
        values,
        colors=colors,
        startangle=90,
        counterclock=False,
        wedgeprops={"width": 0.42, "edgecolor": config.THEME["surface"], "linewidth": 2.5},
    )
    ax.annotate(
        f"{table.iloc[0]['option_selected']}\n{values[0]:.1f}%",
        xy=(0, 0),
        xytext=(0, -0.28),
        ha="center",
        va="center",
        fontsize=13,
        fontweight="bold",
        color=config.THEME["primary"],
    )
    legend_labels = [f"{label} - {value:.1f}%" for label, value in zip(labels, values)]
    ax.legend(
        wedges,
        legend_labels,
        title="Responses",
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        frameon=False,
        fontsize=10,
    )
    question_text = data.loc[data["question_id"] == question_id, "question"].iloc[0]
    ax.set_title(f"{question_text}\n(share of {int(table['votes'].sum()):,} responses)", fontsize=14)
    return _save(fig, "02_headline_donut.png")


# --------------------------------------------------------------------------- #
# 3. Region-wise stacked bar
# --------------------------------------------------------------------------- #
def plot_region_stacked(data: pd.DataFrame, question_id: str = "Q1") -> str:
    """100% stacked bar: option composition inside each region."""
    apply_matplotlib_theme()
    wide = crosstab_share(data, question_id, "region")
    order = wide.sum(axis=1).sort_values(ascending=False).index
    wide = wide.loc[order]

    fig, ax = plt.subplots(figsize=(10.5, 6))
    bottom = np.zeros(len(wide))
    for col_idx, option in enumerate(wide.columns):
        values = wide[option].to_numpy()
        ax.bar(
            wide.index.astype(str),
            values,
            bottom=bottom,
            color=config.CHART_PALETTE[col_idx % len(config.CHART_PALETTE)],
            label=option,
            width=0.62,
            edgecolor=config.THEME["surface"],
            linewidth=1.1,
        )
        for x, (value, base) in enumerate(zip(values, bottom)):
            if value >= 5:  # only label slices big enough to read
                ax.text(
                    x,
                    base + value / 2,
                    f"{value:.0f}%",
                    ha="center",
                    va="center",
                    fontsize=9,
                    color="white",
                    fontweight="bold",
                )
        bottom += values

    ax.set_ylim(0, 100)
    ax.set_ylabel("Share within region (%)")
    ax.set_xlabel("Region")
    question_text = data.loc[data["question_id"] == question_id, "question"].iloc[0]
    ax.set_title(f"Region-wise composition - {question_text}", loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    return _save(fig, "03_region_stacked.png")


# --------------------------------------------------------------------------- #
# 4. Demographic (age group) grouped bar
# --------------------------------------------------------------------------- #
def plot_demographic_comparison(
    data: pd.DataFrame, question_id: str = "Q1", dimension: str = "age_group"
) -> str:
    """Grouped bar chart comparing an option's share across demographic groups."""
    apply_matplotlib_theme()
    long = breakdown_table(data, question_id, dimension)
    options = option_share_table(data, question_id)["option_selected"].tolist()
    groups = sorted(long[dimension].unique().tolist())

    x = np.arange(len(options))
    width = 0.8 / max(len(groups), 1)
    fig, ax = plt.subplots(figsize=(11.5, 6))
    for i, group in enumerate(groups):
        shares = [
            float(long.loc[(long[dimension] == group) & (long["option_selected"] == opt), "share_pct"].sum())
            for opt in options
        ]
        offset = (i - (len(groups) - 1) / 2) * width
        bars = ax.bar(
            x + offset,
            shares,
            width=width * 0.92,
            label=str(group),
            color=config.CHART_PALETTE[i % len(config.CHART_PALETTE)],
        )
        for bar in bars:
            height = bar.get_height()
            if height >= 3:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    height + 0.7,
                    f"{height:.0f}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color=config.THEME["muted"],
                )

    ax.set_xticks(x)
    ax.set_xticklabels([opt.replace(" - ", "\n") for opt in options], fontsize=9)
    ax.set_ylabel(f"Share within {dimension.replace('_', ' ')} (%)")
    ax.set_title(
        f"{data.loc[data['question_id'] == question_id, 'question'].iloc[0]}\nby {dimension.replace('_', ' ').title()}",
        loc="left",
    )
    ax.legend(title=dimension.replace("_", " ").title(), frameon=False, fontsize=9, ncol=len(groups))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    return _save(fig, "04_demographic_comparison.png")


# --------------------------------------------------------------------------- #
# 5. Response trend over time
# --------------------------------------------------------------------------- #
def plot_trend(trend: pd.DataFrame) -> str:
    """Daily response volume with a 7-day rolling average."""
    apply_matplotlib_theme()
    fig, ax = plt.subplots(figsize=(11.5, 5.5))
    ax.fill_between(
        trend["date"],
        trend["responses"],
        color=config.THEME["secondary"],
        alpha=0.16,
    )
    ax.plot(
        trend["date"],
        trend["responses"],
        color=config.THEME["secondary"],
        linewidth=1.6,
        marker="o",
        markersize=3.5,
        label="Daily responses",
    )
    ax.plot(
        trend["date"],
        trend["rolling_7d"],
        color=config.THEME["primary"],
        linewidth=2.8,
        label="7-day rolling average",
    )
    peak = trend.loc[trend["responses"].idxmax()]
    ax.annotate(
        f"Peak: {int(peak['responses'])} responses\n{peak['date']:%d %b %Y}",
        xy=(peak["date"], peak["responses"]),
        xytext=(12, 18),
        textcoords="offset points",
        fontsize=9,
        color=config.THEME["text"],
        arrowprops={"arrowstyle": "->", "color": config.THEME["muted"]},
    )
    ax.set_title("Response volume over the polling window", loc="left")
    ax.set_xlabel("Date")
    ax.set_ylabel("Responses")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.autofmt_xdate()
    fig.tight_layout()
    return _save(fig, "05_response_trend.png")


# --------------------------------------------------------------------------- #
# 6. Heatmap: option share by region
# --------------------------------------------------------------------------- #
def plot_region_heatmap(data: pd.DataFrame, question_id: str = "Q1") -> str:
    """Annotated heatmap of option share per region."""
    apply_matplotlib_theme()
    wide = crosstab_share(data, question_id, "region")
    cmap = LinearSegmentedColormap.from_list(
        "poll_light", ["#FFFFFF", config.THEME["primary"]]
    )
    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    sns.heatmap(
        wide,
        annot=True,
        fmt=".1f",
        cmap=cmap,
        linewidths=1.2,
        linecolor=config.THEME["surface"],
        cbar_kws={"label": "Share within region (%)"},
        ax=ax,
    )
    question_text = data.loc[data["question_id"] == question_id, "question"].iloc[0]
    ax.set_title(f"Heatmap - option share by region\n{question_text}", loc="left")
    ax.set_xlabel("Option selected")
    ax.set_ylabel("Region")
    fig.tight_layout()
    return _save(fig, "06_region_heatmap.png")


# --------------------------------------------------------------------------- #
# 7. Dependency-free word cloud
# --------------------------------------------------------------------------- #
def plot_word_cloud(words: pd.DataFrame, question: str = "Open-ended feedback") -> str:
    """Render a word cloud using a golden-angle sunflower layout (no extra deps)."""
    apply_matplotlib_theme()
    fig, ax = plt.subplots(figsize=(11, 6.5))
    if words.empty:
        ax.text(0.5, 0.5, "No free-text responses available", ha="center", va="center", fontsize=13)
        ax.axis("off")
        return _save(fig, "07_word_cloud.png")

    max_freq = float(words["frequency"].max())
    golden_angle = math.pi * (3 - math.sqrt(5))

    for i, (_, row) in enumerate(words.iterrows()):
        radius = math.sqrt(i + 0.6) * 5.6
        angle = i * golden_angle
        x = radius * math.cos(angle)
        y = radius * math.sin(angle) * 0.62
        size = 9 + 30 * math.sqrt(float(row["frequency"]) / max_freq)
        ax.text(
            x,
            y,
            str(row["word"]),
            fontsize=size,
            color=config.CHART_PALETTE[i % len(config.CHART_PALETTE)],
            ha="center",
            va="center",
            fontweight="bold" if i < 5 else "normal",
            alpha=0.92,
        )

    limit = math.sqrt(len(words)) * 5.6
    ax.set_xlim(-limit * 1.1, limit * 1.1)
    ax.set_ylim(-limit * 0.72, limit * 0.72)
    ax.axis("off")
    ax.set_title(f"What respondents say - word frequency\n{question}", fontsize=14, loc="left")
    return _save(fig, "07_word_cloud.png")


# --------------------------------------------------------------------------- #
# 8. Satisfaction distribution / NPS
# --------------------------------------------------------------------------- #
def plot_satisfaction(data: pd.DataFrame, question_id: str = "Q3") -> str:
    """Satisfaction distribution split into detractors / passives / promoters."""
    apply_matplotlib_theme()
    table = option_share_table(data, question_id)
    scores = pd.to_numeric(
        table["option_selected"].str.extract(r"^(\d)", expand=False), errors="coerce"
    )
    table = table.assign(score=scores).sort_values("score")

    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    colors = [
        config.THEME["danger"] if s <= 2 else config.THEME["accent"] if s == 3 else config.THEME["success"]
        for s in table["score"]
    ]
    bars = ax.bar(table["option_selected"], table["share_pct"], color=colors, width=0.6)
    for bar in bars:
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            f"{bar.get_height():.1f}%",
            ha="center",
            fontsize=10,
            fontweight="medium",
            color=config.THEME["text"],
        )
    promoters = table.loc[table["score"] >= 4, "share_pct"].sum()
    detractors = table.loc[table["score"] <= 2, "share_pct"].sum()
    ax.text(
        0.98,
        0.94,
        f"Promoters (4-5): {promoters:.1f}%\nDetractors (1-2): {detractors:.1f}%\n"
        f"Net score: {promoters - detractors:+.1f} pts",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=10,
        bbox={
            "boxstyle": "round,pad=0.55",
            "facecolor": config.THEME["background"],
            "edgecolor": config.THEME["border"],
        },
    )
    ax.set_ylim(0, max(table["share_pct"].max() * 1.3, 15))
    ax.set_ylabel("Share of responses (%)")
    ax.set_title("Service satisfaction distribution", loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    return _save(fig, "08_satisfaction_distribution.png")


# --------------------------------------------------------------------------- #
# 9. Channel performance
# --------------------------------------------------------------------------- #
def plot_channel_performance(channels: pd.DataFrame) -> str:
    """Dual view: response volume and satisfaction per acquisition channel."""
    apply_matplotlib_theme()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))
    labels = channels["channel"].astype(str).tolist()

    bars = ax1.barh(labels, channels["responses"], color=config.CHART_PALETTE[0], height=0.6)
    _bar_labels(ax1, bars, fmt="{:.0f}", padding=8, fontsize=9)
    ax1.invert_yaxis()
    ax1.set_xlim(0, channels["responses"].max() * 1.2)
    ax1.set_xlabel("Responses")
    ax1.set_title("Responses collected by channel", loc="left")
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.grid(axis="y", visible=False)

    ax2.bar(labels, channels["avg_satisfaction"], color=config.CHART_PALETTE[3], width=0.6)
    ax2.axhline(
        channels["avg_satisfaction"].mean(),
        color=config.THEME["danger"],
        linestyle="--",
        linewidth=1.5,
        label=f"Average {channels['avg_satisfaction'].mean():.2f}",
    )
    ax2.set_ylim(0, 5.4)
    ax2.set_ylabel("Average satisfaction score (1-5)")
    ax2.set_title("Satisfaction by channel", loc="left")
    ax2.tick_params(axis="x", rotation=25)
    ax2.legend(frameon=False, fontsize=9)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.grid(axis="x", visible=False)
    for x, value in enumerate(channels["avg_satisfaction"]):
        ax2.text(x, value + 0.1, f"{value:.2f}", ha="center", fontsize=9, color=config.THEME["text"])

    fig.suptitle("Channel performance", fontsize=15, fontweight="bold", y=1.02)
    fig.tight_layout()
    return _save(fig, "09_channel_performance.png")


# --------------------------------------------------------------------------- #
# 10. Respondent composition
# --------------------------------------------------------------------------- #
def plot_respondent_composition(data: pd.DataFrame) -> str:
    """Four small multiples describing the respondent population."""
    apply_matplotlib_theme()
    dimensions = ["region", "age_group", "gender", "device"]
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5))
    axes = axes.ravel()

    for ax, dim in zip(axes, dimensions):
        counts = (
            data.drop_duplicates(subset=["respondent_id"])[dim]
            .value_counts()
            .sort_values(ascending=False)
        )
        labels = counts.index.astype(str).tolist()
        colors = [config.CHART_PALETTE[i % len(config.CHART_PALETTE)] for i in range(len(counts))]
        wedges, _, autotexts = ax.pie(
            counts,
            labels=labels,
            colors=colors,
            autopct="%1.0f%%",
            startangle=110,
            pctdistance=0.78,
            wedgeprops={"width": 0.45, "edgecolor": config.THEME["surface"], "linewidth": 2},
            textprops={"fontsize": 9.5, "color": config.THEME["text"]},
        )
        for text in autotexts:
            text.set_color("white")
            text.set_fontweight("bold")
            text.set_fontsize(9)
        ax.set_title(
            f"By {dim.replace('_', ' ')} (n={counts.sum():,})",
            fontsize=12,
            loc="left",
        )

    fig.suptitle("Respondent composition", fontsize=16, fontweight="bold", y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    return _save(fig, "10_respondent_composition.png")


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
def generate_all_charts(data: pd.DataFrame, bundle: dict) -> list[str]:
    """Create every chart and return the list of generated file paths."""
    outputs = [
        plot_overall_shares(data),
        plot_donut(data),
        plot_region_stacked(data),
        plot_demographic_comparison(data),
        plot_trend(bundle["trend"]),
        plot_region_heatmap(data),
        plot_word_cloud(bundle["words"]),
        plot_satisfaction(data),
        plot_channel_performance(bundle["channels"]),
        plot_respondent_composition(data),
    ]
    LOGGER.info("Generated %s charts in outputs/charts", len(outputs))
    return outputs


def run_visualization() -> list[str]:
    """Load cleaned data + analysis bundle, then render all charts."""
    from .analysis import full_analysis, load_clean_data

    data = load_clean_data()
    bundle = full_analysis(data)
    return generate_all_charts(data, bundle)


if __name__ == "__main__":  # pragma: no cover - manual execution
    run_visualization()
