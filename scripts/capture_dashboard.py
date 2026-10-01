"""Browser smoke test and genuine README screenshots of the running application.

Start FastAPI and Streamlit first. Install Playwright Chromium with
`python -m playwright install chromium`, or pass --channel chrome for installed Chrome.
"""

import argparse
import json

from playwright.sync_api import expect, sync_playwright

from voc.config import ROOT

TITLES = {
    "Overview": "From customer signals to your next move.",
    "Themes": "What keeps coming up?",
    "Pain Points": "Find the friction that matters.",
    "Objections": "Turn hesitation into a better conversation.",
    "Sentiment": "Understand how customers feel.",
    "Customer Language": "Write in your customers’ words.",
    "Segments": "Understand the people behind the signals.",
    "Campaign Opportunities": "Build campaigns with an evidence trail.",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8501")
    parser.add_argument("--channel", default=None)
    args = parser.parse_args()
    output = ROOT / "docs" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=args.channel, headless=True)
        page = browser.new_page(viewport={"width": 1512, "height": 1100}, device_scale_factor=1)
        page.goto(args.url)
        expect(page.get_by_role("heading", name=TITLES["Overview"], exact=True)).to_be_visible(timeout=90000)
        checked = []
        for name, title in TITLES.items():
            page.get_by_test_id("stRadio").get_by_text(name, exact=True).click()
            expect(page.get_by_role("heading", name=title, exact=True)).to_be_visible(timeout=30000)
            expect(page.locator('[data-testid="stException"]')).to_have_count(0)
            if name in {"Overview", "Campaign Opportunities", "Customer Language", "Sentiment"}:
                # Wait for chart canvas rendering, then capture the real browser viewport.
                page.wait_for_timeout(1200)
                filename = name.lower().replace(" ", "-") + ".png"
                page.screenshot(path=str(output / filename))
                if name == "Campaign Opportunities":
                    page.get_by_role(
                        "heading", name="Get your Mondays back", exact=True
                    ).scroll_into_view_if_needed()
                    page.screenshot(path=str(output / "campaign-brief.png"))
            checked.append(name)
        page.get_by_test_id("stRadio").get_by_text("Overview", exact=True).click()
        expect(page.get_by_role("heading", name=TITLES["Overview"], exact=True)).to_be_visible()
        page.get_by_text("Download the marketing report & campaign backlog", exact=True).click()
        with page.expect_download() as info:
            page.get_by_role("button", name="↓ Marketing report · Markdown").click()
        download = info.value
        download.save_as(str(output / "browser-downloaded-report.md"))
        assert "All demo customer data is synthetic" in (output / "browser-downloaded-report.md").read_text(
            "utf-8"
        )
        page.get_by_text("Download the marketing report & campaign backlog", exact=True).click()
        page.get_by_role("combobox", name="Customer segment", exact=True).click()
        page.get_by_role("option", name="Operations manager", exact=True).click()
        # Recent Streamlit releases virtualize offscreen sidebar widgets.
        page.get_by_test_id("stSidebar").hover()
        page.mouse.wheel(0, 1800)
        page.get_by_role("button", name="Analyze feedback", exact=True).click()
        expect(page.get_by_text("segments: Operations manager", exact=False)).to_be_visible(timeout=30000)
        expect(page.locator('[data-testid="stException"]')).to_have_count(0)
        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.goto(args.url)
        expect(mobile.get_by_role("heading", name=TITLES["Overview"], exact=True)).to_be_visible(
            timeout=90000
        )
        expect(mobile.locator('[data-testid="stException"]')).to_have_count(0)
        expect(mobile.get_by_test_id("stMetricValue").first).to_have_text("640", timeout=30000)
        mobile.wait_for_timeout(1200)
        mobile.screenshot(path=str(output / "mobile-overview.png"))
        browser.close()
    print(
        json.dumps(
            {
                "pages_checked": checked,
                "report_download": "passed",
                "segment_filter": "passed",
                "screenshots": str(output),
            }
        )
    )


if __name__ == "__main__":
    main()
