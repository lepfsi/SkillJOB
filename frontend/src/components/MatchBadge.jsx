import { scoreLevel, LEVEL_LABELS } from "../lib.js";

// Badge de correspondance : score + niveau dérivé (seuils backend).
// Ne se réduit jamais au score : le niveau est toujours affiché.
export default function MatchBadge({ score }) {
  if (score == null || score === undefined) {
    return <span className="badge badge-none">Profil requis</span>;
  }
  const level = scoreLevel(score);
  const cls = level === "forte" ? "badge-strong" : level === "moyenne" ? "badge-medium" : "badge-weak";
  return (
    <span className={`badge ${cls}`}>
      {score}/100 · {LEVEL_LABELS[level]}
    </span>
  );
}
