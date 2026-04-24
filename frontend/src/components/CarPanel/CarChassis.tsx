// SF-24 top-down chassis silhouette
// Ported from design_handoff_f1_cockpit/design/cockpit-car.jsx CarChassis()
// All path data verbatim from the reference; strokes: var(--rule-strong)

export function CarChassis() {
  const stroke = 'var(--rule-strong)'
  const hi = 'var(--text-muted)'

  return (
    <g fill="none" stroke={stroke} strokeWidth="1.1" strokeLinejoin="round" strokeLinecap="round">
      {/* Front wing */}
      <path d="M 60 130 L 340 130 L 340 138 L 60 138 Z" fill="var(--panel)" opacity="0.6" />
      <line x1="60" y1="134" x2="340" y2="134" stroke={hi} strokeWidth="0.5" opacity="0.8" />
      {/* Front wing endplates */}
      <rect x="56" y="126" width="8" height="22" fill="var(--panel)" stroke={stroke} />
      <rect x="336" y="126" width="8" height="22" fill="var(--panel)" stroke={stroke} />

      {/* Nose cone */}
      <path d="M 185 148 L 185 210 L 215 210 L 215 148 Q 215 140 200 140 Q 185 140 185 148 Z"
        fill="var(--panel)" />

      {/* Front suspension arms FL */}
      <line x1="130" y1={230} x2="185" y2="195" stroke={stroke} strokeWidth="1" />
      <line x1="130" y1={250} x2="185" y2="215" stroke={stroke} strokeWidth="1" />
      {/* Front suspension arms FR */}
      <line x1="270" y1={230} x2="215" y2="195" stroke={stroke} strokeWidth="1" />
      <line x1="270" y1={250} x2="215" y2="215" stroke={stroke} strokeWidth="1" />

      {/* Main chassis tub */}
      <path d="M 175 210 L 175 440 Q 175 460 190 460 L 210 460 Q 225 460 225 440 L 225 210 Z"
        fill="var(--panel)" stroke={stroke} />

      {/* Halo */}
      <ellipse cx={200} cy={310} rx="18" ry="14" fill="none" stroke={hi} strokeWidth="0.8" />
      <line x1="200" y1="296" x2="200" y2="330" stroke={hi} strokeWidth="0.6" />

      {/* Cockpit */}
      <ellipse cx={200} cy={315} rx="13" ry="22" fill="#050810" stroke={stroke} strokeWidth="0.8" />

      {/* Sidepods */}
      <path d="M 140 320 Q 135 340 140 360 L 150 440 Q 155 455 175 455 L 175 380 Q 170 340 155 320 Z"
        fill="var(--panel)" stroke={stroke} />
      <path d="M 260 320 Q 265 340 260 360 L 250 440 Q 245 455 225 455 L 225 380 Q 230 340 245 320 Z"
        fill="var(--panel)" stroke={stroke} />

      {/* Airbox */}
      <rect x="193" y="240" width="14" height="30" fill="#050810" stroke={hi} strokeWidth="0.6" />
      <text x="200" y="258" fill={hi} fontFamily="var(--mono)" fontSize="6" textAnchor="middle"
        letterSpacing="0.5">AIRBOX</text>

      {/* Engine / gearbox area */}
      <rect x="180" y="460" width="40" height="120" fill="var(--panel)" stroke={stroke} />
      <line x1="180" y1="480" x2="220" y2="480" stroke={stroke} strokeWidth="0.5" opacity="0.7" />
      <line x1="180" y1="500" x2="220" y2="500" stroke={stroke} strokeWidth="0.5" opacity="0.7" />
      <line x1="180" y1="520" x2="220" y2="520" stroke={stroke} strokeWidth="0.5" opacity="0.7" />
      <line x1="180" y1="540" x2="220" y2="540" stroke={stroke} strokeWidth="0.5" opacity="0.7" />
      <line x1="180" y1="560" x2="220" y2="560" stroke={stroke} strokeWidth="0.5" opacity="0.7" />

      {/* Floor outline */}
      <path d="M 130 280 L 270 280 L 275 650 L 125 650 Z" fill="none" stroke={hi} strokeWidth="0.4"
        strokeDasharray="2 3" opacity="0.6" />

      {/* Rear suspension arms */}
      <line x1="130" y1="580" x2="180" y2="600" stroke={stroke} strokeWidth="1" />
      <line x1="130" y1="620" x2="180" y2="640" stroke={stroke} strokeWidth="1" />
      <line x1="270" y1="580" x2="220" y2="600" stroke={stroke} strokeWidth="1" />
      <line x1="270" y1="620" x2="220" y2="640" stroke={stroke} strokeWidth="1" />

      {/* Rear wing */}
      <path d="M 110 670 L 290 670 L 290 680 L 110 680 Z" fill="var(--panel)" />
      <rect x="106" y="660" width="8" height="30" fill="var(--panel)" stroke={stroke} />
      <rect x="286" y="660" width="8" height="30" fill="var(--panel)" stroke={stroke} />
      {/* DRS line */}
      <line x1="110" y1="674" x2="290" y2="674" stroke={hi} strokeWidth="0.5" />
      <text x="200" y="700" fill={hi} fontFamily="var(--mono)" fontSize="7" textAnchor="middle"
        letterSpacing="1.5">REAR WING · DRS</text>

      {/* Diffuser hint */}
      <path d="M 145 710 L 170 740 M 175 712 L 190 745 M 200 712 L 200 748 M 225 712 L 210 745 M 255 710 L 230 740"
        stroke={hi} strokeWidth="0.5" opacity="0.7" />

      {/* Forward arrow / heading */}
      <g opacity="0.45">
        <line x1="200" y1="90" x2="200" y2="118" stroke="var(--accent)" strokeWidth="1" />
        <path d="M 195 96 L 200 88 L 205 96 Z" fill="var(--accent)" />
        <text x="200" y="82" fill="var(--accent)" fontFamily="var(--mono)" fontSize="7"
          textAnchor="middle" letterSpacing="2">DIR</text>
      </g>
    </g>
  )
}
