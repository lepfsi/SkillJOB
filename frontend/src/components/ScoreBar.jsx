import { LEVEL_LABELS } from "../lib.js";

// Barre de correspondance (§12) : score + niveau + répartition
// couvertes / partielles / manquantes. Jamais un pourcentage isolé.
export default function ScoreBar({ score, covered = 0, partial = 0, missing = 0 }) {
  if (score == null) return null;
  const total = covered + partial + missing;
  const pct = (n) => (total > 0 ? (n / total) * 100 : 0);
  const level = score >= 75 ? "forte" : score >= 45 ? "moyenne" : "faible";
  return (
    <div className="scorebar">
      <div className="scorebar-head">
        <span className="scorebar-value">
          {score}<small> /100</small>
        </span>
        <span className="muted small">
          Correspondance {LEVEL_LABELS[level]}
        </span>
      </div>
      <div className="scorebar-track">
        <div className="scorebar-seg scorebar-seg-covered" style={{ width: `${pct(covered)}%` }} />
        <div className="scorebar-seg scorebar-seg-partial" style={{ width: `${pct(partial)}%` }} />
        <div className="scorebar-seg scorebar-seg-missing" style={{ width: `${pct(missing)}%` }} />
      </div>
      <div className="scorebar-legend">
        <span><b>✓ {covered}</b> couverte(s)</span>
        <span><b>△ {partial}</b> partielle(s)</span>
        <span><b>○ {missing}</b> manquante(s)</span>
      </div>
    </div>
  );
}
