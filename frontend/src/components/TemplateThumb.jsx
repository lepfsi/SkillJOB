import { templateAccentHex } from "../lib.js";

// Aperçu miniature d'un modèle de document : squelette A4 neutre
// (1 ou 2 colonnes, bandeau plat pour le format courriel). Aucune fausse
// donnée : ce sont des traits, pas un faux CV.
export default function TemplateThumb({ template, accent, flat }) {
  const hex = templateAccentHex(template.id, accent) || "#C9D3CD";
  const gray = template.id === "ats";
  const tone = gray ? "#9AA5A0" : hex;
  const cls = [
    "tpl-thumb",
    `tpl-thumb-${template.columns === 2 ? "two" : "one"}`,
    gray ? "tpl-thumb-gray" : "",
    flat ? "flat" : "",
  ].filter(Boolean).join(" ");
  return (
    <span className={cls} aria-hidden="true">
      {template.columns === 2 ? (
        <>
          <span className="tpl-side" style={{ background: tone }} />
          <span className="tpl-body"><i /><i /><i /></span>
        </>
      ) : flat ? (
        <span className="tpl-body"><i /><i /><i /><i /></span>
      ) : (
        <>
          <span className="tpl-head" style={{ background: tone }} />
          <span className="tpl-body"><i /><i /><i /><i /></span>
        </>
      )}
    </span>
  );
}
