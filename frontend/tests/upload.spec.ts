import { test } from '@playwright/test'

test.describe('drag-and-drop session upload (INT-05)', () => {
  test.skip('dropping a .zip triggers POST /api/sessions/upload', async () => {
    // Implemented in Plan 06.
  })
  test.skip('dropping a non-zip shows error toast', async () => {
    // Implemented in Plan 06.
  })
})
