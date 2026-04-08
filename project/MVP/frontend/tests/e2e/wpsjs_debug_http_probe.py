from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "tests" / "artifacts"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:4173"


def dump_page(page, name: str) -> None:
    page.screenshot(path=str(ARTIFACTS / f"{name}.png"), full_page=True)
    print(f"{name.upper()}_TITLE", page.title())
    print(f"{name.upper()}_URL", page.url)
    print(f"{name.upper()}_BODY_TEXT", page.locator("body").inner_text()[:500])
    print(f"{name.upper()}_HAS_APP", page.locator('#app').count() > 0)
    print(f"{name.upper()}_HAS_KNOWLEDGE_BAR", page.locator('[data-testid=\"knowledge-bar\"]').count() > 0)
    print(f"{name.upper()}_HAS_BOTTOM_BAR", page.locator('[data-testid=\"bottom-action-bar\"]').count() > 0)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 380, "height": 900})
        page.on("console", lambda msg: print("CONSOLE", msg.type, msg.text))
        page.on("pageerror", lambda exc: print("PAGEERROR", exc))

        page.goto(f"{BASE}/app.html")
        page.wait_for_load_state("networkidle")
        dump_page(page, "app")

        taskpane = browser.new_page(viewport={"width": 380, "height": 900})
        taskpane.on("console", lambda msg: print("TASKPANE_CONSOLE", msg.type, msg.text))
        taskpane.on("pageerror", lambda exc: print("TASKPANE_PAGEERROR", exc))
        taskpane.goto(f"{BASE}/wps-plugin/taskpane.html")
        taskpane.wait_for_load_state("networkidle")
        dump_page(taskpane, "taskpane")
        browser.close()


if __name__ == "__main__":
    main()
