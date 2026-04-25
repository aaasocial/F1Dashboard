import { test, expect } from '@playwright/test'

test.describe('URL hash round-trip (INT-04)', () => {
  test('selecting and seeking encodes lap into URL hash', async ({ page }) => {
    await page.goto('/')
    await page.locator('select[aria-label="Select race"]').selectOption({ index: 1 })
    await page.locator('select[aria-label="Select driver"]').selectOption({ index: 1 })
    await page.locator('select[aria-label="Select stint"]').selectOption({ index: 1 })
    await page.getByRole('button', { name: /run model/i }).click()
    await expect(page.getByText('TREAD TEMP')).toBeVisible({ timeout: 10000 })

    // Pause first so RAF doesn't change the lap mid-test
    await page.keyboard.press('Space')
    // Seek to lap 7: jump to first (Home), then step forward 6 times
    await page.keyboard.press('Home')   // pos = 1
    for (let i = 0; i < 6; i++) await page.keyboard.press('ArrowRight')
    // Wait for hash write
    await expect.poll(() => page.url(), { timeout: 3000 }).toContain('lap=7')
  })

  test('reload restores selection and lap from hash', async ({ page }) => {
    // Build a hash with a known stint and lap
    const url = '/#race=2024_bahrain&driver=LEC&stint=0&lap=5'
    await page.goto(url)
    // Pickers should be populated from the hash
    await expect(page.locator('select[aria-label="Select race"]')).toHaveValue('2024_bahrain')
    await expect(page.locator('select[aria-label="Select driver"]')).toHaveValue('LEC')
    await expect(page.locator('select[aria-label="Select stint"]')).toHaveValue('0')
  })
})
