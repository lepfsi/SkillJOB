// Anneau de score réutilisable (accueil, mon agent, analyse d'offre).
// `score` : 0-100 ; `text` : libellé central (ex. « 84/100 », « 78 % »).

export default function Ring({ score, text, size = 104, stroke = 8 }) {
  const r = size / 2 - stroke;
  const c = 2 * Math.PI * r;
  const safe = Math.max(0, Math.min(100, score || 0));
  const off = c - (safe / 100) * c;
  const color = safe >= 75 ? "#0e8a63" : safe >= 45 ? "#e67e22" : "#94a3b8";
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      style={{ transform: "rotate(-90deg)" }}
      role="img"
      aria-label={`${safe} sur 100`}
    >
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e6ebe7" strokeWidth={stroke} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={off}
      />
      <text
        x={size / 2}
        y={size / 2 + 5}
        textAnchor="middle"
        style={{ transform: `rotate(90deg)`, transformOrigin: `${size / 2}px ${size / 2}px` }}
        fill={color}
        fontSize={size >= 96 ? 17 : 15}
        fontWeight="700"
        fontFamily="inherit"
      >
        {text}
      </text>
    </svg>
  );
}
