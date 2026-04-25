import { test, expect } from '@playwright/test'

async function selectFirstStintAndRun(page: import('@playwright/test').Page) {
  await page.goto('/')
  // Wait for cascade pickers to populate (MSW returns races immediately)
  await page.locator('select[aria-label="Select race"]').selectOption({ index: 1 })
  await page.locator('select[aria-label="Select driver"]').selectOption({ index: 1 })
  await page.locator('select[aria-label="Select stint"]').selectOption({ index: 1 })
  await page.getByRole('button', { name: /run model/i }).click()
  // Wait for simulation to complete — physics panel renders TREAD TEMP tab
  await expect(page.getByText('TREAD TEMP')).toBeVisible({ timeout: 10000 })
}

test.describe('keyboard shortcuts (INT-01)', () => {
  test('Space toggles play / pause', async ({ page }) => {
    await selectFirstStintAndRun(page)
    // Initial state — playing (button shows PAUSE)
    await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible()
    await page.keyboard.press('Space')
    await expect(page.getByRole('button', { name: 'Play' })).toBeVisible()
    await page.keyboard.press('Space')
    await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible()
  })

  test('? opens shortcuts modal; Esc closes it', async ({ page }) => {
    await page.goto('/')
    await page.keyboard.press('?')
    await expect(page.getByTestId('shortcuts-modal')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByTestId('shortcuts-modal')).toBeHidden()
  })
})
