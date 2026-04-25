import { useState, useRef, useEffect, useCallback } from 'react'
import { useSimulationStore } from '../stores/useSimulationStore'
import { useUIStore } from '../stores/useUIStore'
import { runSimulationStream } from '../lib/sse'

export interface UseDragUploadResult {
  dragActive: boolean
  progress: number          // 0..1
  uploading: boolean
  error: string | null
  /** Manually trigger an upload (used by tests). */
  uploadFile: (file: File) => Promise<{ session_id: string }>
}

function isZipFile(file: File): boolean {
  const nameOk = file.name.toLowerCase().endsWith('.zip')
  // Defense-in-depth MIME check (browser may report empty type for files dragged from some sources)
  const typeOk = file.type === '' || file.type === 'application/zip' || file.type === 'application/x-zip-compressed'
  return nameOk && typeOk
}

/**
 * useDragUpload — Phase 6 INT-05 (D-16/D-17)
 *
 * Registers global document.body listeners for dragenter/dragleave/dragover/drop.
 * Uses dragCounter pattern to prevent flicker when dragging over child elements.
 * Validates .zip extension + MIME type. Uploads via XHR for progress reporting.
 * On success: stores session_id and auto-triggers runSimulationStream if selection is complete.
 */
export function useDragUpload(): UseDragUploadResult {
  const [dragActive, setDragActive] = useState(false)
  const [progress, setProgress] = useState(0)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const dragCounter = useRef(0)
  const abortRef = useRef<XMLHttpRequest | null>(null)

  const uploadFile = useCallback(async (file: File): Promise<{ session_id: string }> => {
    if (!isZipFile(file)) {
      const msg = 'File must be a .zip'
      setError(msg)
      useUIStore.getState().showToast('INVALID FILE — MUST BE .zip')
      throw new Error(msg)
    }
    setUploading(true)
    setError(null)
    setProgress(0)
    try {
      const result = await new Promise<{ session_id: string }>((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        abortRef.current = xhr
        const fd = new FormData()
        fd.append('file', file)
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) setProgress(e.loaded / e.total)
        })
        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try { resolve(JSON.parse(xhr.responseText)) }
            catch { reject(new Error('Invalid JSON response')) }
          } else {
            reject(new Error(`Upload failed (HTTP ${xhr.status})`))
          }
        })
        xhr.addEventListener('error', () => reject(new Error('Network error during upload')))
        xhr.addEventListener('abort', () => reject(new Error('Upload aborted')))
        const apiBase = import.meta.env.VITE_API_URL ?? ''
        xhr.open('POST', `${apiBase}/api/sessions/upload`)
        xhr.send(fd)
      })
      setProgress(1)
      return result
    } catch (e) {
      setError((e as Error).message)
      useUIStore.getState().showToast(`UPLOAD FAILED — ${(e as Error).message.toUpperCase()}`)
      throw e
    } finally {
      setUploading(false)
      abortRef.current = null
    }
  }, [])

  // Auto-trigger simulation after a successful upload, if selection is complete
  const handleSuccess = useCallback((sessionId: string) => {
    const sim = useSimulationStore.getState()
    sim.setSessionId(sessionId)
    useUIStore.getState().showToast(`UPLOAD OK — SESSION ${sessionId.slice(0, 8)}`)
    if (sim.selectedRaceId && sim.selectedDriverCode && sim.selectedStintIndex != null) {
      const controller = new AbortController()
      void runSimulationStream(
        sim.selectedRaceId,
        sim.selectedDriverCode,
        sim.selectedStintIndex,
        controller.signal,
      )
    }
  }, [])

  useEffect(() => {
    if (import.meta.env.DEV) {
      ;(window as any).__testUploadFile = uploadFile
    }
    return () => {
      if (import.meta.env.DEV) delete (window as any).__testUploadFile
    }
  }, [uploadFile])

  useEffect(() => {
    function onDragEnter(e: DragEvent) {
      // Ignore non-file drags (e.g., text selection)
      if (!e.dataTransfer || !e.dataTransfer.types.includes('Files')) return
      e.preventDefault()
      dragCounter.current++
      if (dragCounter.current === 1) setDragActive(true)
    }
    function onDragLeave(e: DragEvent) {
      if (!e.dataTransfer || !e.dataTransfer.types.includes('Files')) return
      dragCounter.current = Math.max(0, dragCounter.current - 1)
      if (dragCounter.current === 0) setDragActive(false)
    }
    function onDragOver(e: DragEvent) {
      if (!e.dataTransfer || !e.dataTransfer.types.includes('Files')) return
      e.preventDefault()  // required to enable drop
    }
    async function onDrop(e: DragEvent) {
      if (!e.dataTransfer) return
      e.preventDefault()
      dragCounter.current = 0
      setDragActive(false)
      const file = e.dataTransfer.files[0]
      if (!file) return
      try {
        const result = await uploadFile(file)
        handleSuccess(result.session_id)
      } catch {
        // error already surfaced via setError + toast in uploadFile
      }
    }
    document.body.addEventListener('dragenter', onDragEnter)
    document.body.addEventListener('dragleave', onDragLeave)
    document.body.addEventListener('dragover', onDragOver)
    document.body.addEventListener('drop', onDrop)
    return () => {
      document.body.removeEventListener('dragenter', onDragEnter)
      document.body.removeEventListener('dragleave', onDragLeave)
      document.body.removeEventListener('dragover', onDragOver)
      document.body.removeEventListener('drop', onDrop)
    }
  }, [uploadFile, handleSuccess])

  return { dragActive, progress, uploading, error, uploadFile }
}
