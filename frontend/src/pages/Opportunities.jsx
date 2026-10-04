import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import MatchBadge from "../components/MatchBadge.jsx";
import { fmtDate, CONTRACT_TYPES } from "../lib.js";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";

// Page Opportunities (§29) : filtres + badge de correspondance sur chaque offre.
export default function Opportunities() {
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState("");
  const [options, setOptions] = useState({ sectors: [], locations: [] });
  const [filters, setFilters] = useState({
    search: "",
    sector: "",
    location: "",
    contract_type: "",
    min_score: "",
  });

  useEffect(() => {
    api("/jobs")
      .then((all) => {
        setOptions({
          sectors: [...new Set(all.map((j) => j.sector))].sort(),
          locations: [...new Set(all.map((j) => j.location))].sort(),
        });
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const params = new URLSearchParams();
    if (filters.search) params.set("search", filters.search);
    if (filters.sector) params.set("sector", filters.sector);
    if (filters.location) params.set("location", filters.location);
    if (filters.contract_type) params.set("contract_type", filters.contract_type);
    if (filters.min_score) params.set("min_score", filters.min_score);
    api(`/jobs?${params.toString()}`)
      .then(setJobs)
      .catch((e) => setError(e.detail));
  }, [filters]);

  const setFilter = (k, v) => setFilters((f) => ({ ...f, [k]: v }));
  const anyMatch = jobs && jobs.some((j) => j.match_score != null);

  return (
    <div className="page">
      <h1>Opportunités</h1>
      <p className="page-lead">
        Emplois, stages, missions et apprentissages collectés à partir de
        sources identifiées et datées.
      </p>

      <div className="filters">
        <label className="field">
          <span>Recherche</span>
          <input
            value={filters.search}
            onChange={(e) => setFilter("search", e.target.value)}
            placeholder="Métier, entreprise, mot-clé…"
          />
        </label>
        <label className="field">
          <span>Secteur</span>
          <select value={filters.sector} onChange={(e) => setFilter("sector", e.target.value)}>
            <option value="">Tous</option>
            {options.sectors.map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Localisation</span>
          <select value={filters.location} onChange={(e) => setFilter("location", e.target.value)}>
            <option value="">Toutes</option>
            {options.locations.map((l) => <option key={l}>{l}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Type de contrat</span>
          <select
            value={filters.contract_type}
            onChange={(e) => setFilter("contract_type", e.target.value)}
          >
            <option value="">Tous</option>
            {CONTRACT_TYPES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Correspondance</span>
          <select
            value={filters.min_score}
            onChange={(e) => setFilter("min_score", e.target.value)}
          >
            <option value="">Toutes</option>
            <option value="75">Forte (≥ 75)</option>
            <option value="45">Moyenne (≥ 45)</option>
          </select>
        </label>
      </div>

      <ErrorNote error={error} />
      {!jobs && !error && <Loader />}

      {jobs && jobs.length === 0 && (
        <Empty title="Aucune offre ne correspond à ces critères">
          <p>Essayez d'élargir vos filtres ou revenez plus tard : de nouvelles opportunités sont ajoutées régulièrement.</p>
        </Empty>
      )}

      {jobs && jobs.length > 0 && (
        <>
          {jobs.some((j) => j.match_score == null) && !anyMatch && (
            <div className="alert alert-info">
              Complétez votre profil pour voir votre correspondance avec chaque
              offre. <Link to="/onboarding">Construire mon profil →</Link>
            </div>
          )}
          <p className="small muted">{jobs.length} offre(s)</p>
          {jobs.map((j) => (
            <Link className="job-row" to={`/opportunites/${j.id}`} key={j.id}>
              <div>
                <div className="job-title">{j.title}</div>
                <div className="job-meta">
                  {j.company} · {j.location} · {j.contract_type} · publiée le {fmtDate(j.published_at)}
                </div>
                <div className="job-meta small">{j.sector}</div>
              </div>
              <MatchBadge score={j.match_score} />
            </Link>
          ))}
        </>
      )}
    </div>
  );
}
