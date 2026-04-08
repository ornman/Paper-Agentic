from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "tests" / "artifacts"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
BASE_URL = "http://127.0.0.1:3889/mvp-preview/app.html"

SSE_BODY = "".join([
    'event: sources\n',
    'data: {"sources":[{"id":1,"document":"文献A","page":7,"content":"理论框架与案例比较能够提升论文论证的完整度。"}]}\n\n',
    'event: chunk\n',
    'data: {"content":"可以先从研究问题切入。"}\n\n',
    'event: chunk\n',
    'data: {"content":"再补充理论框架与案例比较。"}\n\n',
    'event: done\n',
    'data: {"total_tokens":42}\n\n',
])


def shot(page, name: str) -> None:
    page.screenshot(path=str(ARTIFACTS / f"{name}.png"), full_page=True)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 380, "height": 900})

        # 注入最小 WPS 宿主假实现，驱动当前前端的轮询逻辑。
        context.add_init_script(
            """
            window.wps = {
              WpsApplication() {
                return {
                  ActiveDocument: {
                    Name: '论文草稿.docx',
                    Content: {
                      Text: '当前论文正文内容，用于场景 1 灵感生成验证。'
                    }
                  }
                }
              }
            }
            """
        )

        page = context.new_page()

        # mock 知识库和 ask 接口，验证前端真实交互链路。
        def route_handler(route):
            url = route.request.url
            if url.endswith('/api/v1/library/documents'):
                if getattr(route_handler, 'documents_loaded', False):
                    body = '{"code":0,"data":[{"document_id":"doc-1","title":"示例论文","file_path":"D:/papers/example.pdf","index_mode":"brute","status":"completed"}],"message":"success"}'
                else:
                    body = '{"code":0,"data":[],"message":"success"}'
                route.fulfill(status=200, headers={"Content-Type": "application/json"}, body=body)
                return
            if url.endswith('/api/v1/library/import'):
                route_handler.documents_loaded = True
                body = '{"code":0,"data":{"document_id":"doc-1","title":"示例论文","file_path":"D:/papers/example.pdf","index_mode":"brute","status":"pending"},"message":"success"}'
                route.fulfill(status=200, headers={"Content-Type": "application/json"}, body=body)
                return
            if url.endswith('/api/v1/query/ask'):
                route.fulfill(status=200, headers={"Content-Type": "text/event-stream"}, body=SSE_BODY)
                return
            route.continue_()

        route_handler.documents_loaded = False
        page.route('**/*', route_handler)

        page.goto(BASE_URL)
        page.wait_for_selector('[data-testid="knowledge-bar"]')

        # 初始界面截图
        shot(page, '01-initial-shell')
        print('INITIAL_HAS_KNOWLEDGE_BAR', page.locator('[data-testid="knowledge-bar"]').count() > 0)
        print('INITIAL_HAS_BOTTOM_BAR', page.locator('[data-testid="bottom-action-bar"]').count() > 0)

        # 验证错误路径前端拦截
        page.locator('[data-testid="pdf-path-input"]').fill('https://evil.test/a.pdf')
        page.locator('[data-testid="pdf-import-submit"]').click()
        page.wait_for_timeout(200)
        print('INVALID_PATH_MESSAGE', page.locator('[data-testid="pdf-import-message"]').inner_text())
        shot(page, '02-invalid-path')

        # 验证导入成功后知识库状态
        page.locator('[data-testid="pdf-path-input"]').fill('D:/papers/example.pdf')
        page.locator('[data-testid="pdf-import-submit"]').click()
        page.wait_for_timeout(400)
        print('POST_IMPORT_TEXT', page.locator('body').inner_text()[:400])
        shot(page, '03-import-success')

        # 验证灵感按钮闭环
        ask_button = page.locator('[data-testid="bottom-action-bar"] .primary-button')
        ask_button.click()
        page.wait_for_timeout(400)
        body_text = page.locator('body').inner_text()
        print('HAS_MESSAGE_LIST', page.locator('[data-testid="message-list"]').count() > 0)
        print('HAS_SOURCE_CARD_LIST', page.locator('[data-testid="source-card-list"]').count() > 0)
        print('HAS_ACTION_TEXT', '基于当前论文草稿获取灵感' in body_text)
        print('HAS_SOURCE_TEXT', '文献A' in body_text)
        shot(page, '04-ask-inspiration-success')

        browser.close()


if __name__ == '__main__':
    main()
