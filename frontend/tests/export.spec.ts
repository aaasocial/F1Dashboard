import { test, expect } from '@playwright/test'

async function loadStint(page: import('@playwright/test').Page) {
  await page.goto('/')
  await page.locator('select[aria-label="Select race"]').selectOption({ index: 1 })
  await page.locator('select[aria-label="Select driver"]').selectOption({ index: 1 })
  await page.locator('select[aria-label="Select stint"]').selectOption({ index: 1 })
  await page.getByRole('button', { name: /run model/i }).click()
  await expect(page.getByText('TREAD TEMP')).toBeVisible({ timeout: 10000 })
}

test.describe('chart export (INT-02)', () => {
  test('right-click PhysicsPanel opens custom context menu', async ({ page }) => {
    await loadStint(page)
    await page.evaluate(() => {
      const el = document.querySelector('[role="tabpanel"]')
      if (!el) throw new Error('tabpanel not found')
      el.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX: 400, clientY: 400 }))
    })
    await expect(page.getByTestId('chart-context-menu')).toBeVisible()
    await expect(page.getByText('Export PNG')).toBeVisible()
    await expect(page.getByText('Export SVG')).toBeVisible()
    await expect(page.getByText('Export CSV')).toBeVisible()
  })

  test('Export CSV triggers a download', async ({ page }) => {
    await loadStint(page)
    await page.evaluate(() => {
      const el = document.querySelector('[role="tabpanel"]')
      if (!el) throw new Error('tabpanel not found')
      el.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX: 400, clientY: 400 }))
    })
    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 5000 }),
      page.getByText('Export CSV').click(),
    ])
    expect(download.suggestedFilename()).toMatch(/\.csv$/)
  })
})
