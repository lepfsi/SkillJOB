import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { STATUS_LABELS } from "../../lib.js";
import { Loader, ErrorNote } from "../../components/ui.jsx";

// Analyse institutionnelle (§39, V3) : indicateurs AGREGÉS et anonymisés
// pour les décideurs publics — lecture du marché local des compétences.

function BarList({ title, items, labelKey, valueKey, unit }) {
  if (!items || items.length === 0) return null;
  const max = Math.max(...items.map((i) => i[valueKey])) || 1;
  return (
    <div className="panel">
      <h2>{title}</h2>
      {items.slice(0, 10).map((item) => (
        <div key={String(item[labelKey])} style={{ margin: "0.35rem 0" }}>
          <div className="small" style={{ display: "flex", justifyContent: "space-between" }}>
            <span>{item[labelKey]}</span>
            <span className="muted">{item[valueKey]} {unit}</span>
          </div>
          <div className="scorebar-track">
            <div
              className="scorebar-seg scorebar-seg-covered"
              style={{ width: `${(item[valueKey] / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function AdminInstitutional() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/admin/institutional-dashboard")
      .then(setData)
      .catch((e) => setError(e.detail));
  }, []);

  if (error) return <div className="page"><ErrorNote error={error} /></div>;
  if (!data) return <div className="page"><Loader /></div>;

  return (
    <div className="page">
      <h1>Analyse institutionnelle</h1>
      <p className="page-lead">
        Lecture agrégée et anonymisée du marché local (§39) : volume d'usage,
        offre et demande de compétences, écarts structurants pour orienter
        les politiques de formation. Aucune donnée individuelle.
      </p>

      <div className="metric-strip">
        <div className="metric"><strong>{data.candidates}</strong><span>jeunes inscrits</span></div>
        <div className="metric"><strong>{data.profiles_with_skills}</strong><span>profils avec compétences</span></div>
        <div className="metric"><strong>{data.recruiters}</strong><span>entreprises</span></div>
        <div className="metric"><strong>{data.jobs}</strong><span>offres référencées</span></div>
        <div className="metric"><strong>{data.applications}</strong><span>candidatures</span></div>
      </div>

      <div className="grid-2">
        <BarList
          title="Compétences les plus demandées par les offres"
          items={data.top_demand} labelKey="skill" valueKey="count" unit="demandes"
        />
        <BarList
          title="Compétences les plus disponibles chez les jeunes"
          items={data.top_supply} labelKey="skill" valueKey="count" unit="profils"
        />
      </div>

      {data.skill_gaps.length > 0 && (
        <div className="panel">
          <h2>Écarts de compétences (demande forte, vivier faible)</h2>
          <p className="small muted">
            Priorités pour les programmes de formation : compétences
            recherchées par les offres mais rares dans le vivier de talents.
          </p>
          <div className="table-wrap">
            <table className="skills">
              <thead>
                <tr>
                  <th>Compétence</th>
                  <th>Demande (offres)</th>
                  <th>Vivier (profils)</th>
                  <th>Tension</th>
                </tr>
              </thead>
              <tbody>
                {data.skill_gaps.map((g) => (
                  <tr key={g.skill}>
                    <td>{g.skill}</td>
                    <td>{g.demand}</td>
                    <td>{g.supply}</td>
                    <td>
                      <span className="badge badge-medium">×{g.ratio}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="grid-2">
        <BarList
          title="Répartition géographique des jeunes"
          items={data.regions} labelKey="region" valueKey="candidates" unit="jeunes"
        />
        <BarList
          title="Secteurs qui recrutent"
          items={data.sectors} labelKey="sector" valueKey="offers" unit="offres"
        />
      </div>

      {data.applications_by_status.length > 0 && (
        <div className="panel">
          <h2>Candidatures par étape</h2>
          <ul className="trend-list">
            {data.applications_by_status.map((s) => (
              <li key={s.status}>
                <span>{STATUS_LABELS[s.status] || s.status}</span>
                <span className="trend">{s.count}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
