import { ACCENTS } from "../lib.js";

// Choix de la couleur d'accent (personnalisation sans invention) :
// « Modèle » garde la couleur propre au modèle choisi. Partagé entre
// le détail d'offre (génération ciblée) et la page Documents (CV
// généraliste). Une couleur libre #RRGGBB est acceptée en plus du catalogue.
export default function AccentRow({ accent, onPick }) {
  const custom = /^#[0-9A-Fa-f]{6}$/.test(accent || "");
  return (
    <div className="tpl-accent-row">
      <span className="tpl-accent-label">Couleur d'accent</span>
      <button
        type="button"
        className={`tpl-swatch tpl-swatch-default${accent === "" ? " active" : ""}`}
        onClick={() => onPick("")}
        title="Couleur propre au modèle"
      >
        Modèle
      </button>
      {ACCENTS.map((a) => (
        <button
          key={a.key}
          type="button"
          className={`tpl-swatch${accent === a.key ? " active" : ""}`}
          style={{ background: a.hex }}
          onClick={() => onPick(a.key)}
          title={a.label}
          aria-label={a.label}
        />
      ))}
      <label
        className={`tpl-swatch tpl-swatch-custom${custom ? " active" : ""}`}
        style={{ background: custom ? accent : "conic-gradient(#D9534F, #D9A21B, #3FBF8F, #3AA6E0, #7C5CE0, #D9534F)" }}
        title="Couleur personnalisée"
      >
        <input
          type="color"
          value={custom ? accent : "#7C5CE0"}
          onChange={(e) => onPick(e.target.value.toUpperCase())}
          aria-label="Choisir une couleur personnalisée"
        />
        <span aria-hidden="true">{custom ? "" : "+"}</span>
      </label>
      <span className="tpl-accent-note">
        Les modèles ATS et classiques suivent aussi la couleur choisie.
      </span>
    </div>
  );
}
