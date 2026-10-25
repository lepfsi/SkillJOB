import { Link } from "react-router-dom";
import { Icon, I, ArrowIcon } from "./icons.jsx";

// Carte agent de la colonne latérale. Elle apparaît sur les pages qui
// n'ont pas de bandeau agent en haut : l'agent reste joignable, connaît
// la page courante (`page`) et oriente ses conseils en conséquence.
// `prompt` prépare une question propre à la page (envoyée à l'ouverture).

export default function AgentSideCard({ page, title, hint, prompt }) {
  const params = new URLSearchParams();
  if (page) params.set("page", page);
  if (prompt) params.set("q", prompt);
  const href = `/assistant${params.toString() ? `?${params.toString()}` : ""}`;

  return (
    <section className="dash-card agent-side">
      <div className="agent-side-head">
        <span className="agent-side-icon"><Icon d={I.bot} size={19} /></span>
        <div className="agent-side-copy">
          <h2>{title || "Mon agent"}</h2>
          <p>{hint || "Une question sur cette page ? Ori peut vous aider, à partir de vos données réelles."}</p>
        </div>
      </div>
      <Link className="btn btn-primary btn-small agent-side-cta" to={href}>
        Discuter avec l'agent <ArrowIcon direction="right" size={11} />
      </Link>
    </section>
  );
}
