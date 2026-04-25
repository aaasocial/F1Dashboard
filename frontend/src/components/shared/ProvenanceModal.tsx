import { useSimulationStore } from '../../stores/useSimulationStore'
import { useUIStore } from '../../stores/useUIStore'

const DISCLAIMER = 'Unofficial fan tool — not affiliated with F1, FIA, or Pirelli.'

export function ProvenanceModal() {
  const open = useUIStore(s => s.provenanceOpen)
  const setOpen = useUIStore(s => s.setProvenanceOpen)
  const data = useSimulationStore(s => s.data)

  if (!open) return null

  const meta = data?.meta
  const rows: Array<[string, string]> = [
    ['FastF1 version',         meta?.fastf1_version ?? 'N/A'],
    ['Model schema version',   meta?.model_schema_version ?? 'N/A'],
    ['Calibration ID',         meta != null ? String(meta.calibration_id) : 'N/A'],
    ['Calibration date',       'N/A'],   // Not in current meta schema (per D-20)
    ['Run ID',                 meta?.run_id ?? 'N/A'],
  ]

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Provenance and disclaimer"
      data-testid="provenance-modal"
      onClick={() => setOpen(false)}
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(5,7,11,0.85)',
        backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--mono)',
      }}
    >
      <div
        data-testid="provenance-modal-content"
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--panel)',
          border: '1px solid var(--rule-strong)',
          borderRadius: 0,
          padding: '24px 28px',
          minWidth: 520,
          color: 'var(--text)',
          fontFamily: 'var(--mono)',
          fontSize: 11,
          letterSpacing: 1.2,
        }}
      >
        <div style={{
          fontSize: 10, color: 'var(--accent)', letterSpacing: 2.4, fontWeight: 700,
          marginBottom: 16,
        }}>DATA PROVENANCE</div>
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <tbody>
            {rows.map(([label, value]) => (
              <tr key={label} data-testid={`prov-row-${label.replace(/\s+/g, '-').toLowerCase()}`}>
                <td style={{
                  padding: '5px 16px 5px 0',
                  color: 'var(--text-dim)',
                  whiteSpace: 'nowrap',
                }}>{label}</td>
                <td style={{
                  padding: '5px 0',
                  color: 'var(--text)',
                  fontWeight: 600,
                  textAlign: 'right',
                }}>{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{
          marginTop: 22,
          padding: '10px 12px',
          borderTop: '1px solid var(--rule)',
          fontSize: 10,
          color: 'var(--text-dim)',
          letterSpacing: 1.2,
          lineHeight: 1.5,
        }}>{DISCLAIMER}</div>
        <div style={{
          marginTop: 14, fontSize: 9, color: 'var(--text-muted)', letterSpacing: 1.4,
        }}>
          ESC OR CLICK OUTSIDE TO CLOSE
        </div>
      </div>
    </div>
  )
}
