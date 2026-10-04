import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { PROFICIENCY_LABELS, SOURCE_LABELS } from "../lib.js";
import { TrendIcon } from "../components/icons.jsx";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";

// Page Skills (§32) : matrice de compétences avec niveau, source,
// preuves et demande du marché.
export default function Skills() {
  const [profile, setProfile] = useState(undefined);
  const [market, setMarket] = useState(null);

  useEffect(() => {
    api("/profile").then(setProfile).catch(() => setProfile(null));
    api("/skills/market").then(setMarket).catch(() => {});
  }, []);

  if (profile === undefined) {
    return <div className="page"><Loader /></div>;
  }
  if (profile === null) {
    return (
      <div className="page">
        <h1>Compétences</h1>
        <Empty title="Aucun profil pour le moment">
          <p>Construisez votre profil pour voir votre matrice de compétences.</p>
          <Link className="btn btn-primary" to="/onboarding">Construire mon profil</Link>
        </Empty>
      </div>
    );
  }

  const demandMap = {};
  (market || []).forEach((m) => {
    demandMap[m.name] = m;
  });

  const skills = profile.skills || [];
  if (skills.length === 0) {
    return (
      <div className="page">
        <h1>Compétences</h1>
        <Empty title="Aucune compétence enregistrée">
          <p>Ajoutez vos compétences depuis la page Profil.</p>
          <Link className="btn btn-outline" to="/profil">Modifier mon profil</Link>
        </Empty>
      </div>
    );
  }

  const byCategory = {};
  skills.forEach((s) => {
    const cat = s.category || "Autres";
    (byCategory[cat] = byCategory[cat] || []).push(s);
  });

  return (
    <div className="page">
      <h1>Compétences</h1>
      <p className="page-lead">
        Votre matrice de compétences : niveau, source, preuves issues de votre
        profil, et demande observée sur le marché. Modifiez vos compétences
        depuis la page <Link to="/profil">Profil</Link>.
      </p>

      <div className="table-wrap">
        <table className="skills">
          <thead>
            <tr>
              <th>Compétence</th>
              <th>Niveau</th>
              <th>Source</th>
              <th>Preuves</th>
              <th>Marché</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(byCategory).map(([cat, items]) => (
              [
                <tr className="cat-row" key={`cat-${cat}`}>
                  <td colSpan="5">{cat}</td>
                </tr>,
                ...items.map((s) => {
                  const m = demandMap[s.skill];
                  return (
                    <tr key={s.skill}>
                      <td>{s.skill}</td>
                      <td>{PROFICIENCY_LABELS[s.proficiency] || s.proficiency}</td>
                      <td>{SOURCE_LABELS[s.source] || s.source}</td>
                      <td>{s.evidence_count}</td>
                      <td>
                        {m ? (
                          <span className={`trend trend-${m.trend}`}>
                            <TrendIcon trend={m.trend} /> {m.demand_count} offre(s)
                          </span>
                        ) : (
                          <span className="muted small">Non demandée</span>
                        )}
                      </td>
                    </tr>
                  );
                }),
              ]
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
