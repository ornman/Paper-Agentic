from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "tests" / "artifacts"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

APP_URL = f"file:///{(ROOT / 'dist' / 'app.html').as_posix()}"
TASKPANE_URL = f"file:///{(ROOT / 'dist' / 'wps-plugin' / 'taskpane.html').as_posix()}"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        app_page = browser.new_page(viewport={"width": 380, "height": 900})
        app_page.goto(APP_URL)
        app_page.wait_for_load_state("networkidle")
        app_page.screenshot(path=str(ARTIFACTS / "frontend-app.png"), full_page=True)
        app_text = app_page.locator("body").inner_text()
        print("APP_HAS_KNOWLEDGE_BAR", app_page.locator('[data-testid="knowledge-bar"]').count() > 0)
        print("APP_HAS_BOTTOM_BAR", app_page.locator('[data-testid="bottom-action-bar"]').count() > 0)
        print("APP_HAS_EMPTY_STATE", '论文创作辅助' in app_text)

        taskpane_page = browser.new_page(viewport={"width": 380, "height": 900})
        taskpane_page.goto(TASKPANE_URL)
        taskpane_page.wait_for_load_state("networkidle")
        taskpane_page.screenshot(path=str(ARTIFACTS / "frontend-taskpane.png"), full_page=True)
        taskpane_text = taskpane_page.locator("body").inner_text()
        print("TASKPANE_HAS_APP_ROOT", taskpane_page.locator('#app').count() > 0)
        print("TASKPANE_HAS_RENDERED_UI", '论文创作辅助' in taskpane_text)

        browser.close()


if __name__ == "__main__":
    main()
