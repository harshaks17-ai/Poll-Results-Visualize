"""End-to-end browser test of the running Streamlit dashboard.

Covers: console/page errors, every tab, filter interactions, question switching
and CSV upload. Prints a PASS/FAIL report. Run from the project root.
"""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "test_evidence"
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:8501"
CHROME = r"C:\Users\harah\AppData\Local\ms-playwright\chromium-1243\chrome-win64\chrome.exe"

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" -> {detail}" if detail else ""))


def wait_for_server(timeout: int = 90) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(URL, timeout=3)
            return True
        except Exception:
            time.sleep(2)
    return False


def wait_for_charts(page, settle: int = 3000) -> int:
    """Wait for *visible* Plotly SVGs to be drawn; return how many rendered."""
    page.wait_for_timeout(settle)
    rendered = 0
    for _ in range(20):
        rendered = (
            page.evaluate(
                "[...document.querySelectorAll('.js-plotly-plot svg')]"
                ".filter(s => s.getBoundingClientRect().width > 0).length"
            )
            or 0
        )
        if rendered:
            break
        page.wait_for_timeout(800)
    page.wait_for_timeout(2500)
    return rendered


def _server_up() -> bool:
    try:
        urllib.request.urlopen(URL, timeout=3)
        return True
    except Exception:
        return False


def main() -> int:
    RESULTS.clear()
    if not wait_for_server():
        record("server reachable", False, f"{URL} did not respond")
        return 1
    record("server reachable", True, URL)

    console_errors: list[str] = []
    page_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME, args=["--no-sandbox", "--force-color-profile=srgb"]
        )
        page = browser.new_page(viewport={"width": 1500, "height": 1150}, device_scale_factor=2)
        page.set_default_timeout(20_000)
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)))

        page.goto(URL, wait_until="networkidle")
        rendered = wait_for_charts(page, 8000)
        record("initial render", rendered >= 2, f"{rendered} chart(s) drawn")

        hero = page.get_by_text("Poll Results Visualizer").first
        record("hero heading visible", hero.is_visible())
        kpi_labels = page.locator(".kpi .label")
        record(
            "KPI tiles rendered",
            kpi_labels.count() == 5 and kpi_labels.first.is_visible(),
            f"{kpi_labels.count()} tiles",
        )

        # ---- every tab renders charts -------------------------------------
        tabs = ["Overview", "Regions", "Demographics", "Trend", "Text insights", "Data"]
        for tab in tabs:
            page.get_by_role("tab", name=tab).click()
            page.wait_for_timeout(1500)
            count = wait_for_charts(page, 3000)
            visible_text = page.inner_text("body")
            record(
                f"tab '{tab}' renders",
                count >= 1 or tab == "Data",
                f"{count} chart(s)",
            )
            page.screenshot(path=str(OUT / f"tab_{tab.lower().replace(' ', '_')}.png"))

        # ---- back to overview, exercise the question selector --------------
        page.get_by_role("tab", name="Overview").click()
        page.wait_for_timeout(1200)
        page.get_by_label("Question").first.click()
        page.wait_for_timeout(700)
        page.get_by_role("option", name="Q3").first.click()
        wait_for_charts(page, 3500)
        body = page.inner_text("body")
        record("question switch -> Q3", "How satisfied" in body)
        page.screenshot(path=str(OUT / "question_switched_to_Q3.png"))

        # ---- apply a region filter -----------------------------------------
        page.get_by_label("Region").first.click()
        page.wait_for_timeout(700)
        page.get_by_role("option", name="North").first.click()
        page.wait_for_timeout(600)
        page.keyboard.press("Escape")
        page.wait_for_timeout(800)
        sidebar_text = page.locator("[data-testid='stSidebar']").inner_text()
        wait_for_charts(page, 3500)
        record("region filter = North", "North" in sidebar_text)
        page.screenshot(path=str(OUT / "filter_region_north.png"))

        # ---- CSV upload path ------------------------------------------------
        file_input = page.locator("input[type='file']")
        if file_input.count() > 0:
            raw_csv = ROOT / "data" / "raw" / "poll_responses_raw.csv"
            file_input.first.set_input_files(str(raw_csv))
            page.wait_for_timeout(9000)
            body = page.inner_text("body")
            uploaded = "Loaded and cleaned your export" in body or "rows" in body
            record("CSV upload accepted", uploaded, raw_csv.name)
            page.screenshot(path=str(OUT / "csv_uploaded.png"))
        else:
            record("CSV upload accepted", False, "file input not found")

        # ---- cleaned data tab download button ------------------------------
        page.get_by_role("tab", name="Data").click()
        page.wait_for_timeout(2500)
        record("data preview table", page.locator("[data-testid='stDataFrame']").count() >= 1)
        record(
            "download button present",
            page.get_by_text("Download cleaned dataset").count() >= 1,
        )

        browser.close()

    # ---- console / page errors -------------------------------------------
    filtered = [e for e in console_errors if "favicon" not in e.lower()]
    record("no page errors", not page_errors, str(page_errors[:2]) if page_errors else "")
    record("no console errors", not filtered, str(filtered[:2]) if filtered else "")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("\n" + "=" * 64)
    print(f"{passed}/{len(RESULTS)} checks passed")
    print("=" * 64)
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"FAILED: {name} {detail}")
    print(f"evidence screenshots -> {OUT.relative_to(ROOT)}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())


# --------------------------------------------------------------------------- #
# Pytest entry point - starts the dashboard itself if it is not already up
# --------------------------------------------------------------------------- #
def test_browser_dashboard_end_to_end() -> None:
    """Run the whole browser check suite, managing the Streamlit server."""
    launched = None
    if not _server_up():
        launched = subprocess.Popen(
            [
                sys.executable, "-m", "streamlit", "run", "dashboard.py",
                "--server.headless", "true", "--browser.gatherUsageStats", "false",
            ],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    try:
        rc = main()
        assert rc == 0, f"{sum(1 for _, ok, _ in RESULTS if not ok)} browser check(s) failed"
    finally:
        if launched is not None:
            # Windows: kill the whole process tree, otherwise the port stays bound.
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(launched.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
