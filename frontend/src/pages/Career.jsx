import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import MatchBadge from "../components/MatchBadge.jsx";
import SkillTag from "../components/SkillTag.jsx";
import { ACCESSIBILITY_LABELS } from "../lib.js";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";

// Page Career (§33) : métiers compatibles + lecture du marché (§13).
const TREND_ARROW = { up: "↑", stable: "→", down: "↓" };

function MarketPanel({ market }) {
  if (!market) return null;
  return (
    <section className="panel">
      <h2>Marché observé</h2>
      <div className="grid-2">
        <div>
          <h3>Compétences les plus demandées</h3>
          <ul className="trend-list">
            {market.top_skills.slice(0, 8).map((s) => (
              <li key={s.name}>
                <span>{s.name}</span>
                <span className="trend">{s.count} offre(s)</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3>En hausse</h3>
          <div className="chip-row">
            {market.trending_up.length > 0
              ? market.trending_up.map((s) => <span key={s} className="chip">{TREND_ARROW.up} {s}</span>)
              : <span className="muted small">Aucune hausse marquée</span>}
          </div>
          <h3>En baisse</h3>
          <div className="chip-row">
            {market.trending_down.length > 0
              ? market.trending_down.map((s) => <span key={s} className="chip">{TREND_ARROW.down} {s}</span>)
              : <span className="muted small">Aucune baisse marquée</span>}
          </div>
          <h3>Émergentes</h3>
          <div className="chip-row">
            {market.emerging.length > 0
              ? market.emerging.map((s) => <span key={s} className="chip chip-warn">{s}</span>)
              : <span className="muted small">Non demandée</span>}
          </div>
        </div>
      </div>
      <h3>Secteurs qui recrutent</h3>
      <ul className="trend-list">
        {market.sectors.slice(0, 6).map((s) => (
          <li key={s.name}>
            <span>{s.name}</span>
            <span className="trend">{s.offers} offre(s)</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function Career() {
  const [careers, setCareers] = useState(null);
  const [market, setMarket] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api("/careers").catch((e) => setError(e.detail)),
      api("/market/trends").catch(() => {}),
    ]).then(([c, m]) => {
      if (c) setCareers(c);
      setMarket(m || null);
    });
  }, []);

  if (error && !careers) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!careers) {
    return <div className="page"><Loader /></div>;
  }

  return (
    <div className="page">
      <h1>Carrière</h1>
      <p className="page-lead">
        Métiers compatibles avec votre profil, accessibles immédiatement ou
        après une montée en compétences. L'orientation est une aide à la
        décision, pas une prescription.
      </p>

      <MarketPanel market={market} />

      {careers.length === 0 && (
        <Empty title="Aucune recommandation disponible">
          <p>Construisez d'abord votre profil pour obtenir des orientations personnalisées.</p>
        </Empty>
      )}

      {careers.map((c) => (
        <section className="panel" key={c.id}>
          <div className="job-head">
            <div>
              <h2 style={{ marginBottom: 0 }}>{c.title}</h2>
              <p className="job-meta">
                {c.family} · {ACCESSIBILITY_LABELS[c.match.accessibility] || c.match.accessibility}
              </p>
            </div>
            <MatchBadge score={c.match.score} />
          </div>
          <p>{c.description}</p>

          <div className="chip-row">
            {c.match.covered.map((s) => <SkillTag key={s} name={s} state="covered" />)}
            {c.match.missing.map((s) => <SkillTag key={`m-${s}`} name={s} state="missing" />)}
          </div>

          {c.match.recommended_actions.length > 0 && (
            <>
              <h3>Actions recommandées</h3>
              <ul className="explain-list">
                {c.match.recommended_actions.map((a, i) => <li key={i}>{a}</li>)}
              </ul>
            </>
          )}

          {c.required_skills.length > 0 && (
            <>
              <h3>Compétences du métier</h3>
              <div className="chip-row">
                {c.required_skills.map((rs) => (
                  <SkillTag key={rs.name} name={rs.name} state="neutral" importance={rs.importance} />
                ))}
              </div>
            </>
          )}

          {c.related_jobs && c.related_jobs.length > 0 && (
            <>
              <h3>Offres ouvertes liées à ce métier</h3>
              <div className="chip-row">
                {c.related_jobs.map((j) => (
                  <Link key={j.id} className="chip" to={`/opportunites/${j.id}`}>
                    {j.title} · {j.company} · {j.location}
                  </Link>
                ))}
              </div>
            </>
          )}
        </section>
      ))}
    </div>
  );
}
