import { describe, expect, it } from 'vitest'
import { createWpsHostAdapter } from '../wps-host'

function getTaskpaneEntryHtml(): string {
  const taskpane = document.createElement('html')
  taskpane.innerHTML = `
    <body>
      <div id="app"></div>
      <script type="module" src="../src/main.ts"></script>
    </body>
  `
  return taskpane.innerHTML
}

describe('createWpsHostAdapter', () => {
  it('exposes a host adapter that can start polling and report document availability', async () => {
    const host = createWpsHostAdapter({
      WpsApplication() {
        return {
          ActiveDocument: {
            Name: '测试论文.docx',
            Content: {
              Text: '这是正文内容',
            },
          },
        }
      },
    })

    await host.startPolling()

    expect(host.getSnapshot()).toEqual({
      available: true,
      docTitle: '测试论文.docx',
      text: '这是正文内容',
      updatedAt: expect.any(String),
    })
  })

  it('returns an unavailable snapshot when the host API is missing', async () => {
    const host = createWpsHostAdapter(undefined)

    await host.startPolling()

    expect(host.getSnapshot()).toEqual({
      available: false,
      docTitle: '',
      text: '',
      updatedAt: null,
    })
  })

  it('keeps taskpane entry on the same window context instead of using iframe dist indirection', () => {
    const taskpaneHtml = getTaskpaneEntryHtml()

    expect(taskpaneHtml).not.toContain('<iframe')
    expect(taskpaneHtml).not.toContain('../dist/app.html')
    expect(taskpaneHtml).toContain('../src/main.ts')
  })
})
