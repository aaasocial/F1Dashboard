import { test, expect } from '@playwright/test'

test.describe('tire widget clipboard copy (INT-03)', () => {
  test('right-click CarFooter cell shows COPIED toast', async ({ page, context }) => {
    // Grant clipboard permissions for chromium
    await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    await page.goto('/')
    await page.locator('select[aria-label="Select race"]').selectOption({ index: 1 })
    await page.locator('select[aria-label="Select driver"]').selectOption({ index: 1 })
    await page.locator('select[aria-label="Select stint"]').selectOption({ index: 1 })
    await page.getByRole('button', { name: /run model/i }).click()
    await expect(page.getByText('TREAD TEMP')).toBeVisible({ timeout: 10000 })

    // Right-click the FRONT·L axle label in the CarFooter (FL corner cell)
    const flCell = page.getByText('FRONT·L').first()
    await flCell.click({ button: 'right' })
    await expect(page.getByTestId('toast')).toContainText('COPIED FL')
  })
})
