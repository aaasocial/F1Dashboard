import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useDragUpload } from './useDragUpload'
import { useSimulationStore } from '../stores/useSimulationStore'
import { useUIStore } from '../stores/useUIStore'

function fireDragEvent(type: string, files: File[] = []): DragEvent {
  const dt = {
    types: files.length > 0 ? ['Files'] : [],
    files,
  } as unknown as DataTransfer
  const e = new Event(type, { bubbles: true, cancelable: true }) as DragEvent
  Object.defineProperty(e, 'dataTransfer', { value: dt, configurable: true })
  document.body.dispatchEvent(e)
  return e
}

beforeEach(() => {
  useSimulationStore.setState({
    data: null, loading: false, error: null, moduleProgress: null,
    selectedRaceId: null, selectedDriverCode: null, selectedStintIndex: null,
    sessionId: null, lastRunParams: null,
  })
  useUIStore.setState({
    hoveredLap: null, hoveredCorner: null, mode: 'live',
    playing: true, pos: 1.0, speed: 1,
    statusLogCollapsed: false, xZoom: null, mapFullscreen: false,
    shortcutsOpen: false, provenanceOpen: false, toastMessage: null,
  })
})

describe('useDragUpload — initial state', () => {
  it('returns dragActive=false initially', () => {
    const { result } = renderHook(() => useDragUpload())
    expect(result.current.dragActive).toBe(false)
  })
})

describe('useDragUpload — drag listeners', () => {
  it('dragenter with files sets dragActive=true', () => {
    const { result } = renderHook(() => useDragUpload())
    act(() => { fireDragEvent('dragenter', [new File([''], 'a.zip')]) })
    expect(result.current.dragActive).toBe(true)
  })
  it('dragleave matched by dragenter returns dragActive=false', () => {
    const { result } = renderHook(() => useDragUpload())
    act(() => { fireDragEvent('dragenter', [new File([''], 'a.zip')]) })
    act(() => { fireDragEvent('dragleave', [new File([''], 'a.zip')]) })
    expect(result.current.dragActive).toBe(false)
  })
  it('two dragenters then one dragleave keeps dragActive=true (counter pattern)', () => {
    const { result } = renderHook(() => useDragUpload())
    act(() => { fireDragEvent('dragenter', [new File([''], 'a.zip')]) })
    act(() => { fireDragEvent('dragenter', [new File([''], 'a.zip')]) })
    act(() => { fireDragEvent('dragleave', [new File([''], 'a.zip')]) })
    expect(result.current.dragActive).toBe(true)
  })
})

describe('useDragUpload — uploadFile validation', () => {
  it('rejects non-zip files', async () => {
    const { result } = renderHook(() => useDragUpload())
    const txt = new File(['hi'], 'a.txt', { type: 'text/plain' })
    await expect(result.current.uploadFile(txt)).rejects.toThrow(/zip/i)
    await waitFor(() => {
      expect(result.current.error).toBeTruthy()
    })
    expect(useUIStore.getState().toastMessage).toBe('INVALID FILE — MUST BE .zip')
  })
  it('accepts .zip and posts to /api/sessions/upload', async () => {
    const { result } = renderHook(() => useDragUpload())
    const zip = new File(['fakezip'], 'cache.zip', { type: 'application/zip' })
    const out = await result.current.uploadFile(zip)
    expect(out.session_id).toBe('test-session-abc123')
  })
})
