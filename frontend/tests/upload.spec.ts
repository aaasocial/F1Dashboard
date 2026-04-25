import { test, expect } from '@playwright/test'

test.describe('drag-and-drop session upload (INT-05)', () => {
  test('dropping a non-zip surfaces error toast', async ({ page }) => {
    await page.goto('/')
    await page.waitForFunction(() => typeof (window as any).__testUploadFile === 'function')
    await page.evaluate(async () => {
      const file = new File(['hi'], 'notes.txt', { type: 'text/plain' })
      try {
        await (window as any).__testUploadFile(file)
      } catch {
        // expected — invalid file rejects
      }
    })
    await expect(page.getByTestId('toast')).toContainText('INVALID FILE — MUST BE .zip')
  })

  test('dropping a .zip triggers POST /api/sessions/upload (MSW returns mock session)', async ({ page }) => {
    await page.goto('/')
    await page.waitForFunction(() => typeof (window as any).__testUploadFile === 'function')
    const [req] = await Promise.all([
      page.waitForRequest('**/api/sessions/upload'),
      page.evaluate(async () => {
        const file = new File([new Uint8Array([0x50, 0x4b, 0x03, 0x04])], 'cache.zip', { type: 'application/zip' })
        try {
          await (window as any).__testUploadFile(file)
        } catch {
          // errors ok
        }
      }),
    ])
    expect(req.method()).toBe('POST')
  })
})
