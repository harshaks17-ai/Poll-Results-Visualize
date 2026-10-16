"""
Poll Results Visualizer - command line entry point.

Usage (from the project root):
    python main.py all          # generate -> clean -> analyse -> charts -> insights
    python main.py generate     # create the raw synthetic poll export
    python main.py clean        # clean the raw export
    python main.py analyze      # statistics + JSON summary
    python main.py visualize    # render all charts
    python main.py insights     # Markdown insight report
    python main.py dashboard    # launch the Streamlit dashboard
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # allow `python main.py`

from src import config  # noqa: E402
from src import analysis, data_cleaning, data_generator, insights, visualization  # noqa: E402
from src.utils import banner, ensure_directories, get_logger  # noqa: E402

LOGGER = get_logger()


def _print_console_summary(bundle: dict) -> None:
    """Pretty-print the headline numbers so the console output is useful proof."""
    overall = bundle["overall"]
    print()
    print(banner("POLL RESULTS - HEADLINE NUMBERS"))
    print(
        f"Responses : {overall['responses']:,}    Respondents : {overall['respondents']:,}"
        f"    Window : {overall['date_from']} -> {overall['date_to']}"
    )
    print(f"Avg satisfaction : {overall['avg_satisfaction']}/5")
    print()
    for summary in bundle["question_summaries"]:
        print(f"  {summary['question_id']}  {summary['question'][:60]}")
        print(
            f"      leader : {summary['leading_option']} "
            f"({summary['leading_share_pct']:.1f}%, MoE +/-{summary['margin_of_error_95']} pts)"
        )
        print(
            f"      runner-up : {summary['runner_up_option']} "
            f"({summary['runner_up_share_pct']:.1f}%)  ->  lead {summary['lead_margin_pct']:.1f} pts"
        )
        if "net_promoter_score" in summary:
            print(
                f"      scale : mean {summary['mean_score']}/5, "
                f"net {summary['net_promoter_score']:+.1f} pts"
            )
        print()
    print(banner("OUTPUTS WRITTEN"))
    for path in (
        config.CLEAN_CSV_PATH,
        config.SUMMARY_JSON_PATH,
        config.INSIGHTS_MD_PATH,
        config.QUALITY_MD_PATH,
        config.CHARTS_DIR,
    ):
        print(f"  - {path.relative_to(config.PROJECT_ROOT)}")
    print(banner())


def cmd_generate() -> None:
    data_generator.generate_and_save()


def cmd_clean():
    return data_cleaning.run_cleaning()


def cmd_analyze():
    return analysis.run_analysis()


def cmd_visualize():
    return visualization.run_visualization()


def cmd_insights():
    return insights.run_insights()


def cmd_all() -> None:
    ensure_directories()
    print(banner("PHASE 1/5  GENERATE SYNTHETIC POLL DATA"))
    data_generator.generate_and_save()

    print(banner("PHASE 2/5  CLEAN & VALIDATE"))
    clean, _ = data_cleaning.run_cleaning()

    print(banner("PHASE 3/5  ANALYSE"))
    bundle = analysis.run_analysis(clean)

    print(banner("PHASE 4/5  VISUALISE"))
    visualization.generate_all_charts(clean, bundle)

    print(banner("PHASE 5/5  GENERATE INSIGHTS"))
    insights.run_insights(bundle)

    _print_console_summary(bundle)


def cmd_dashboard() -> None:
    """Launch the Streamlit dashboard."""
    import subprocess

    dashboard = config.PROJECT_ROOT / "dashboard.py"
    LOGGER.info("Launching Streamlit dashboard (%s)...", dashboard.name)
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(dashboard)], check=False)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="Poll Results Visualizer",
        description="Clean, analyse and visualise poll / survey results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python main.py all\n"
            "  python main.py clean && python main.py analyze\n"
            "  python main.py dashboard\n"
        ),
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=["all", "generate", "clean", "analyze", "visualize", "insights", "dashboard"],
        help="pipeline stage to run (default: all)",
    )
    args = parser.parse_args(argv)

    ensure_directories()
    handlers = {
        "all": cmd_all,
        "generate": cmd_generate,
        "clean": cmd_clean,
        "analyze": cmd_analyze,
        "visualize": cmd_visualize,
        "insights": cmd_insights,
        "dashboard": cmd_dashboard,
    }
    handlers[args.command]()


if __name__ == "__main__":
    main()
