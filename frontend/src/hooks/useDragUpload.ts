import { useState, useRef, useEffect, useCallback } from 'react'

export interface UseDragUploadResult {
  dragActive: boolean
  progress: number          // 0..1
  uploading: boolean
  error: string | null
  /** Manually trigger an upload (used by tests). */
  uploadFile: (file: File) => Promise<{ session_id: string }>
}

/**
 * useDragUpload — Phase 6 D-16/D-17.
 * Plan 05 wires global document.body dragenter/dragleave/dragover/drop.
 * Plan 01 ships only the state shape and uploadFile so tests can import it.
 */
export function useDragUpload(): UseDragUploadResult {
  const [dragActive, setDragActive] = useState(false)
  const [progress, setProgress] = useState(0)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const dragCounter = useRef(0)

  const uploadFile = useCallback(async (file: File): Promise<{ session_id: string }> => {
    if (!file.name.toLowerCase().endsWith('.zip')) {
      setError('File must be a .zip')
      throw new Error('File must be a .zip')
    }
    setUploading(true)
    setError(null)
    setProgress(0)
    try {
      const result = await new Promise<{ session_id: string }>((resolve, reject) => {
        const xhr = new XMLHttpRequest()
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
        const apiBase = import.meta.env.VITE_API_URL ?? ''
        xhr.open('POST', `${apiBase}/api/sessions/upload`)
        xhr.send(fd)
      })
      setProgress(1)
      return result
    } catch (e) {
      setError((e as Error).message)
      throw e
    } finally {
      setUploading(false)
    }
  }, [])

  // Plan 05 will add the document.body event listeners here.
  useEffect(() => {
    // Placeholder — full implementation in Plan 05.
    // Referencing scaffold state setters to satisfy TypeScript noUnusedLocals.
    void dragCounter
    void setDragActive
  }, [])

  return { dragActive, progress, uploading, error, uploadFile }
}
