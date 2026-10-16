"""
Smoke test: run the Streamlit dashboard headlessly and assert it renders
without exceptions.

Usage:  python -m pytest tests/test_dashboard.py -q      (or) python tests/test_dashboard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from streamlit.testing.v1 import AppTest


def test_dashboard_runs() -> None:
    at = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "dashboard.py"), default_timeout=120
    )
    at.run()

    exceptions = at.exception
    if exceptions:
        for error in exceptions:
            print(f"ERROR {type(error.value).__name__}: {error.value}")
            trace = getattr(error, "stack_trace", None)
            if trace:
                print(trace)
    assert not exceptions, f"Dashboard raised {len(exceptions)} exception(s)"

    # Sanity check: the hero heading and at least one chart should be present.
    assert any("Poll Results Visualizer" in str(m.value) for m in at.markdown)
    assert len(at.get("plotly_chart")) >= 5, "Expected several plotly charts to render"
    assert not at.error


def test_dashboard_filters() -> None:
    """Select a different question and confirm the app re-renders cleanly."""
    at = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "dashboard.py"), default_timeout=120
    )
    at.run()
    selectors = at.get("selectbox")
    if selectors:
        target = next((s for s in selectors if s.label == "Question"), selectors[0])
        target.specs = None  # no-op guard
        target.set_value("Q3").run()
        assert not at.exception


if __name__ == "__main__":
    test_dashboard_runs()
    print("Dashboard smoke test PASSED")
    test_dashboard_filters()
    print("Dashboard filter test PASSED")
