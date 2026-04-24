import { describe, it, expect } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useDragUpload } from './useDragUpload'

describe('useDragUpload (scaffold)', () => {
  it('returns initial state with dragActive=false, progress=0, uploading=false, error=null', () => {
    const { result } = renderHook(() => useDragUpload())
    expect(result.current.dragActive).toBe(false)
    expect(result.current.progress).toBe(0)
    expect(result.current.uploading).toBe(false)
    expect(result.current.error).toBeNull()
    expect(typeof result.current.uploadFile).toBe('function')
  })
})
