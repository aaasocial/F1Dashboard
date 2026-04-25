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
    const tabpanel = page.locator('[role="tabpanel"]').first()
    await tabpanel.click({ button: 'right', position: { x: 100, y: 100 } })
    await expect(page.getByTestId('chart-context-menu')).toBeVisible()
    await expect(page.getByText('Export PNG')).toBeVisible()
    await expect(page.getByText('Export SVG')).toBeVisible()
    await expect(page.getByText('Export CSV')).toBeVisible()
  })

  test('Export CSV triggers a download', async ({ page }) => {
    await loadStint(page)
    const tabpanel = page.locator('[role="tabpanel"]').first()
    await tabpanel.click({ button: 'right', position: { x: 100, y: 100 } })
    const dlPromise = page.waitForEvent('download', { timeout: 5000 })
    await page.getByText('Export CSV').click()
    const download = await dlPromise
    expect(download.suggestedFilename()).toMatch(/\.csv$/)
  })
})
