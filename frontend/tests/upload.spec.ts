import { test, expect } from '@playwright/test'

test.describe('drag-and-drop session upload (INT-05)', () => {
  test('dropping a non-zip surfaces error toast', async ({ page }) => {
    await page.goto('/')
    // Build a DataTransfer with a fake .txt file and dispatch drop on document.body
    await page.evaluate(() => {
      const file = new File(['hi'], 'notes.txt', { type: 'text/plain' })
      const dt = new DataTransfer()
      dt.items.add(file)
      const opts = { bubbles: true, cancelable: true, dataTransfer: dt }
      document.body.dispatchEvent(new DragEvent('dragenter', opts))
      document.body.dispatchEvent(new DragEvent('dragover', opts))
      document.body.dispatchEvent(new DragEvent('drop', opts))
    })
    await expect(page.getByTestId('toast')).toContainText('INVALID FILE — MUST BE .zip')
  })

  test('dropping a .zip triggers POST /api/sessions/upload (MSW returns mock session)', async ({ page }) => {
    await page.goto('/')
    // Use Playwright's request interception to confirm the call
    const reqPromise = page.waitForRequest('**/api/sessions/upload')
    await page.evaluate(() => {
      const file = new File([new Uint8Array([0x50, 0x4b, 0x03, 0x04])], 'cache.zip', { type: 'application/zip' })
      const dt = new DataTransfer()
      dt.items.add(file)
      const opts = { bubbles: true, cancelable: true, dataTransfer: dt }
      document.body.dispatchEvent(new DragEvent('dragenter', opts))
      document.body.dispatchEvent(new DragEvent('dragover', opts))
      document.body.dispatchEvent(new DragEvent('drop', opts))
    })
    const req = await reqPromise
    expect(req.method()).toBe('POST')
  })
})
