// Symboles imposés par le cahier des charges (§12, §30) :
// ✓ couverte · △ partielle · ○ manquante.
const SYMBOLS = { covered: "✓", partial: "△", missing: "○" };
const LABELS = { covered: "couverte", partial: "partielle", missing: "manquante" };

export default function SkillTag({ name, state, importance }) {
  const sym = SYMBOLS[state] || "";
  const imp = importance ? (
    <span className="skill-importance">{importance === "core" ? "essentielle" : "appréciée"}</span>
  ) : null;
  return (
    <span className={`skill-tag skill-${state || "neutral"}`} title={state ? `Compétence ${LABELS[state]}` : ""}>
      {sym} {name} {imp}
    </span>
  );
}
