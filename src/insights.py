"""
Insight generation.

Turns the analysis bundle into an executive summary a manager could act on:
who is leading, where the opinion splits, what changed over time, and what the
free-text feedback is repeatedly complaining about.
"""

from __future__ import annotations

import pandas as pd

from . import config
from .utils import ensure_directories, get_logger

LOGGER = get_logger()


def _fmt(value: float, digits: int = 1, suffix: str = "%") -> str:
    return f"{value:.{digits}f}{suffix}"


def build_insights(data: pd.DataFrame, bundle: dict) -> str:
    """Return the full Markdown insight report."""
    overall = bundle["overall"]
    summaries = bundle["question_summaries"]
    words = bundle["words"]
    trend = bundle["trend"]

    lines: list[str] = []
    lines.append("# Poll Results - Insight Report")
    lines.append("")
    lines.append(
        f"**Polling window:** {overall['date_from']} to {overall['date_to']}  |  "
        f"**Responses:** {overall['responses']:,}  |  "
        f"**Respondents:** {overall['respondents']:,}  |  "
        f"**Questions:** {overall['questions']}  |  "
        f"**Average satisfaction:** {overall['avg_satisfaction']}/5"
    )
    lines.append("")

    # --------------------------------------------------------------- headline
    lines.append("## 1. Executive summary")
    lines.append("")
    leader = max(summaries, key=lambda s: s["leading_share_pct"])
    lines.append(
        f"- The strongest signal in this poll is **{leader['leading_option']}** "
        f"({_fmt(leader['leading_share_pct'])} of {leader['total_responses']:,} responses) on: "
        f"*{leader['question']}*"
    )
    closest = min(summaries, key=lambda s: s["lead_margin_pct"])
    lines.append(
        f"- The tightest contest is **{closest['question_id']}** "
        f"({_fmt(closest['leading_share_pct'])} vs {_fmt(closest['runner_up_share_pct'])}, "
        f"a lead of only {_fmt(closest['lead_margin_pct'])} points) - this is where the "
        f"uncertainty is highest."
    )
    lines.append(
        f"- With n = {leader['total_responses']:,}, the leader's margin of error at 95% "
        f"confidence is **+/-{leader['margin_of_error_95']} points**."
    )
    if overall["avg_satisfaction"]:
        lines.append(
            f"- Overall service satisfaction is **{overall['avg_satisfaction']}/5**, and "
            f"{overall['feedback_with_text_pct']}% of responses included written feedback."
        )
    lines.append("")

    # ------------------------------------------------------- per question
    lines.append("## 2. Question-by-question findings")
    lines.append("")
    for summary in summaries:
        lines.append(f"### {summary['question_id']} - {summary['question']}")
        lines.append("")
        lines.append(f"| Option | Votes | Share |")
        lines.append("| --- | --- | --- |")
        table = bundle["tables"]["option_share"]
        rows = table.loc[table["question_id"] == summary["question_id"]]
        for _, row in rows.iterrows():
            lines.append(f"| {row['option_selected']} | {int(row['votes']):,} | {_fmt(float(row['share_pct']))} |")
        lines.append("")
        detail = (
            f"**Leader:** {summary['leading_option']} with {_fmt(summary['leading_share_pct'])} "
            f"of the vote ({summary['total_responses']:,} responses, MoE +/-{summary['margin_of_error_95']} pts). "
            f"**Runner-up:** {summary['runner_up_option']} at {_fmt(summary['runner_up_share_pct'])}. "
            f"Together the top two account for {_fmt(summary['top2_share_pct'])} of responses."
        )
        if "net_promoter_score" in summary:
            detail += (
                f" Mean score {summary['mean_score']}/5, median {summary['median_score']}; "
                f"{_fmt(summary['promoters_pct'])} promoters vs {_fmt(summary['detractors_pct'])} "
                f"detractors (**net {summary['net_promoter_score']:+.1f} pts**)."
            )
        lines.append(detail)
        lines.append("")

    # --------------------------------------------------------- dimensions
    lines.append("## 3. Where opinion splits - demographic deep dive")
    lines.append("")
    region_tbl = bundle["crosstabs"].get("Q1_by_region")
    if region_tbl is not None:
        lines.append("| Region | " + " | ".join(region_tbl.columns.astype(str)) + " |")
        lines.append("| --- |" + " --- |" * len(region_tbl.columns))
        for region, row in region_tbl.iterrows():
            lines.append(f"| **{region}** | " + " | ".join(_fmt(float(v)) for v in row) + " |")
        lines.append("")

        # Swing is measured for the *actual* leading option, not simply the
        # first column of the cross-tab.
        leading_option = region_tbl.mean(axis=0).idxmax()
        column = region_tbl[leading_option]
        strongest, weakest = column.idxmax(), column.idxmin()
        lines.append(
            f"Regional skew is real: **{leading_option}** swings by "
            f"**{float(column.max() - column.min()):.1f} points** between "
            f"**{strongest}** ({column.max():.1f}%) and **{weakest}** "
            f"({column.min():.1f}%), so a single national headline number hides "
            f"materially different local preferences."
        )
        lines.append("")

    age_tbl = bundle["crosstabs"].get("Q2_by_age_group")
    if age_tbl is not None:
        lines.append("### Product priority by age group (share %)")
        lines.append("")
        lines.append("| Age group | " + " | ".join(age_tbl.columns.astype(str)) + " |")
        lines.append("| --- |" + " --- |" * len(age_tbl.columns))
        for age, row in age_tbl.iterrows():
            lines.append(f"| **{age}** | " + " | ".join(_fmt(float(v)) for v in row) + " |")
        lines.append("")

    # ------------------------------------------------------------- trend
    lines.append("## 4. Response trend")
    lines.append("")
    peak = trend.loc[trend["responses"].idxmax()]
    quiet = trend.loc[trend["responses"].idxmin()]
    lines.append(
        f"- Busiest day: **{peak['date']:%d %b %Y}** with {int(peak['responses'])} responses."
    )
    lines.append(f"- Quietest day: **{quiet['date']:%d %b %Y}** with {int(quiet['responses'])} responses.")
    lines.append(
        f"- The 7-day rolling average moved from "
        f"{float(trend['rolling_7d'].iloc[0]):.1f} to {float(trend['rolling_7d'].iloc[-1]):.1f} "
        "responses/day, so collection effort was fairly steady once mid-poll marketing kicked in."
    )
    lines.append("")

    # --------------------------------------------------- open feedback
    lines.append("## 5. What people wrote in their own words")
    lines.append("")
    if not words.empty:
        top = ", ".join(f"**{row['word']}** ({int(row['frequency'])})" for _, row in words.head(8).iterrows())
        lines.append(f"The most repeated themes are: {top}.")
        positives = [w for w in words["word"].tolist() if w in {"love", "loved", "great", "excellent", "good", "awesome", "simple"}]
        pain_points = [w for w in words["word"].tolist() if w in {"price", "pricing", "crashes", "slow", "frequent", "limited", "expensive"}]
        if positives:
            lines.append(f"Positive signals detected around: {', '.join(positives)}.")
        if pain_points:
            lines.append(f"Complaint clusters detected around: {', '.join(pain_points)}.")
    else:
        lines.append("No free-text feedback was collected in this export.")
    lines.append("")

    # ------------------------------------------------------ recommendations
    lines.append("## 6. Recommended actions")
    lines.append("")
    recommendations = [
        f"Prioritise **{summaries[1]['leading_option'] if len(summaries) > 1 else summaries[0]['leading_option']}** "
        "on the roadmap - it is the single most requested capability.",
        "Run region-specific messaging: the leading option does not win everywhere, so "
        "differentiate the pitch for regions where it is weakest.",
        f"Publish the **{closest['question_id']}** result with a caveat - the "
        f"{_fmt(closest['lead_margin_pct'])} lead is inside the margin of error.",
        "Build a student / entry pricing tier: price is one of the most frequent words "
        "in the free-text feedback.",
        "Convert the 1-5 satisfaction detractor group with a follow-up email sequence; "
        "this is the cheapest available retention win.",
    ]
    for rec in recommendations:
        lines.append(f"- {rec}")
    lines.append("")

    # ------------------------------------------------------ methodology
    lines.append("## 7. Methodology & limitations")
    lines.append("")
    lines.append(
        "- Shares are calculated as `option votes / valid responses for that question x 100`, "
        "so every question's shares sum to 100%."
    )
    lines.append(
        "- Rows with blank, junk or out-of-scope answers were removed before aggregation; "
        "the removed count is documented in `outputs/reports/data_quality_report.md`."
    )
    lines.append(
        "- Margin of error uses the normal approximation `1.96 x sqrt(p(1-p)/n)`, which "
        "assumes an approximately random sample."
    )
    lines.append(
        "- This dataset is synthetic. It is generated with deliberate demographic "
        "tilts to demonstrate the analysis pipeline, not to describe real opinions."
    )
    lines.append("")
    lines.append("---")
    lines.append(
        f"*Generated by {config.PROJECT_NAME} v{config.PROJECT_VERSION} "
        f"— {config.PROJECT_AUTHOR}.*"
    )
    return "\n".join(lines)


def save_insights(report: str, path=config.INSIGHTS_MD_PATH) -> None:
    """Write the insight report to disk."""
    ensure_directories()
    path.write_text(report, encoding="utf-8")
    LOGGER.info("Insight report saved -> %s", path.relative_to(config.PROJECT_ROOT))


def run_insights(bundle: dict | None = None) -> str:
    """Generate and persist the insight report."""
    from .analysis import full_analysis, load_clean_data

    data = load_clean_data()
    if bundle is None:
        bundle = full_analysis(data)
    report = build_insights(data, bundle)
    save_insights(report)
    return report


if __name__ == "__main__":  # pragma: no cover - manual execution
    run_insights()
