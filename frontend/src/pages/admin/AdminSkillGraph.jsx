import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";

// Skill Graph (§41, V3) : exploration du graphe compétences ↔ métiers ↔
// offres ↔ talents ↔ formations. Détecte des trajectoires possibles même
// sans intitulé de poste exact.

export default function AdminSkillGraph() {
  const [entry, setEntry] = useState(null);
  const [node, setNode] = useState(null);
  const [skill, setSkill] = useState("");
  const [error, setError] = useState("");
  const [loadingNode, setLoadingNode] = useState(false);

  useEffect(() => {
    api("/admin/skill-graph").then(setEntry).catch((e) => setError(e.detail));
  }, []);

  async function explore(name) {
    setLoadingNode(true);
    setNode(null);
    setError("");
    try {
      const res = await api(`/admin/skill-graph?skill=${encodeURIComponent(name)}`);
      setNode(res);
      setSkill(name);
    } catch (err) {
      setError(err.detail);
    } finally {
      setLoadingNode(false);
    }
  }

  return (
    <div className="page">
      <h1>Skill Graph</h1>
      <p className="page-lead">
        Graphe national des compétences (§41) : pour chaque compétence, les
        métiers associés, les offres ouvertes, le vivier de talents par
        niveau et les compétences voisines qui dessinent des trajectoires.
      </p>
      <ErrorNote error={error} />

      {entry && (
        <div className="panel">
          <h2>Points d'entrée : compétences structurantes</h2>
          <p className="small muted">
            Demandées par les offres (demande) et présentes chez les jeunes
            (vivier). Cliquez pour explorer le nœud.
          </p>
          <div className="chip-row">
            {entry.entry_points.map((e) => (
              <button
                key={e.skill}
                type="button"
                className={`chip${skill === e.skill ? " chip-warn" : ""}`}
                onClick={() => explore(e.skill)}
              >
                {e.skill}
                <span className="skill-importance">{e.demand} offres</span>
              </button>
            ))}
          </div>
        </div>
      )}
      {!entry && !error && <Loader />}

      {loadingNode && <Loader label="Exploration du graphe…" />}

      {node && (
        <div>
          <section className="panel">
            <div className="section-head">
              <h2 style={{ margin: 0 }}>
                {node.node.skill}
                <span className="badge badge-strong" style={{ marginLeft: "0.6rem" }}>
                  {node.node.category || "Compétence"}
                </span>
              </h2>
            </div>
            <div className="metric-strip" style={{ margin: "0.8rem 0" }}>
              <div className="metric"><strong>{node.jobs_count}</strong><span>offre(s) ouverte(s)</span></div>
              <div className="metric"><strong>{node.careers.length}</strong><span>métier(s) associé(s)</span></div>
              <div className="metric"><strong>{node.talents_count}</strong><span>talent(s) dans le vivier</span></div>
              <div className="metric"><strong>{node.learning.length}</strong><span>formation(s) référencée(s)</span></div>
            </div>
          </section>

          {node.careers.length > 0 && (
            <section className="panel">
              <h2>Métiers exigeant cette compétence</h2>
              <div className="chip-row">
                {node.careers.map((c) => (
                  <span key={c.id} className="chip">{c.title}<span className="skill-importance">{c.family}</span></span>
                ))}
              </div>
            </section>
          )}

          {node.jobs.length > 0 && (
            <section className="panel">
              <h2>Offres ouvertes</h2>
              {node.jobs.map((j) => (
                <p key={j.id} className="small" style={{ margin: "0.2rem 0" }}>
                  {j.title} · {j.company} · {j.location}
                </p>
              ))}
            </section>
          )}

          {node.talents_by_level.length > 0 && (
            <section className="panel">
              <h2>Vivier par niveau de maîtrise</h2>
              <ul className="trend-list">
                {node.talents_by_level.map((l) => (
                  <li key={l.level}>
                    <span>{l.level === "avance" ? "Avancé" : l.level === "intermediaire" ? "Intermédiaire" : "Débutant"}</span>
                    <span className="trend">{l.count} talent(s)</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {node.related_skills.length > 0 && (
            <section className="panel">
              <h2>Compétences voisines (trajectoires)</h2>
              <p className="small muted">
                Co-occurrences dans les métiers et les offres : la combinaison
                de cette compétence avec ses voisines ouvre les métiers listés
                ci-dessus.
              </p>
              <div className="chip-row">
                {node.related_skills.map((r) => (
                  <button
                    key={r.skill}
                    type="button"
                    className="chip"
                    onClick={() => explore(r.skill)}
                  >
                    {r.skill}
                    <span className="skill-importance">poids {r.weight}</span>
                  </button>
                ))}
              </div>
            </section>
          )}

          {node.learning.length > 0 && (
            <section className="panel">
              <h2>Formations référencées</h2>
              <ul className="explain-list">
                {node.learning.map((l) => (
                  <li key={l.title}>{l.title} · {l.provider}</li>
                ))}
              </ul>
            </section>
          )}

          {node.careers.length === 0 && node.jobs_count === 0 && (
            <Empty title="Compétence isolée">
              <p>Aucun métier ni offre ne l'exige pour l'instant dans la base.</p>
            </Empty>
          )}
        </div>
      )}
    </div>
  );
}
