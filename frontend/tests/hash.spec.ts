import { test } from '@playwright/test'

test.describe('URL hash round-trip (INT-04)', () => {
  test.skip('selecting race+driver+stint+lap encodes into hash', async () => {
    // Implemented in Plan 06.
  })
  test.skip('reload restores selection and lap from hash', async () => {
    // Implemented in Plan 06.
  })
})
