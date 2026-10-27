import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client.js";
import {
  CONTRACT_TYPES, LEVEL_LABELS, fmtDate, initialsOf, plural, scoreLevel,
} from "../lib.js";
import { Icon, I, ArrowIcon } from "../components/icons.jsx";
import Ring from "../components/Ring.jsx";
import AgentSideCard from "../components/AgentSideCard.jsx";
import JobVisual from "../components/JobVisual.jsx";
import { Loader, ErrorNote } from "../components/ui.jsx";
import { useDomains } from "../components/DomainPicker.jsx";

// Offres d'emploi (maquette « Page offre ») : la meilleure opportunité est
// mise en avant, suivie de la liste complète avec onglets de correspondance,
// filtres et tri. Chaque chiffre vient de l'API et reste explicable (§12) :
// un score n'est jamais affiché seul, il est toujours accompagné de son
// niveau et du détail couverte / partielle / manquante.

const TABS = [
  { key: "all", label: "Toutes" },
  { key: "forte", label: "Meilleures correspondances" },
  { key: "moyenne", label: "À votre portée" },
  { key: "faible", label: "À développer" },
];

function scoreClass(score) {
  const level = scoreLevel(score);
  if (level === "forte") return "strong";
  if (level === "moyenne") return "medium";
  return "weak";
}

// « Publié il y a 8 jours » tant que l'offre est récente, puis la date exacte.
function publishedLabel(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (days <= 0) return "Publié aujourd'hui";
  if (days === 1) return "Publié hier";
  if (days < 30) return `Publié il y a ${days} jours`;
  return `Publiée le ${fmtDate(iso)}`;
}

// Symboles imposés par le cahier des charges (§12) :
// ✓ couverte · △ partielle · ○ manquante.
function MatchMarks({ covered = [], partial = [], missing = [] }) {
  return (
    <>
      {covered.map((s) => (
        <li key={`c-${s}`}><span className="mk mk-ok">✓</span>{s}</li>
      ))}
      {partial.map((s) => (
        <li key={`p-${s}`}><span className="mk mk-part">△</span>{s}</li>
      ))}
      {missing.map((s) => (
        <li key={`m-${s}`}><span className="mk mk-miss">○</span>{s}</li>
      ))}
    </>
  );
}

// Contenu d'une ligne d'offre : partagé entre le mode normal (ligne
// cliquable) et le mode « choisir une offre » (action d'adaptation).
function OppRowMain({ j, domains }) {
  return (
    <>
      <JobVisual job={j} domains={domains} variant="row" />
      <span className="opps-row-main">
        <span className="opps-row-top">
          <strong>{j.title}</strong>
          {j.match_score != null && (
            <span className={`opps-score opps-score-${scoreClass(j.match_score)}`}>
              {j.match_score}/100
            </span>
          )}
        </span>
        <span className="opps-row-meta">
          <span><Icon d={I.briefcase} size={12} /> {j.company}</span>
          <span><Icon d={I.pin} size={12} /> {j.location}</span>
          <span>{j.contract_type}</span>
          <span><Icon d={I.clock} size={12} /> {publishedLabel(j.published_at)}</span>
        </span>
        <span className="opps-row-tags">
          {j.sector && <span className="opps-tag opps-tag-sector">{j.sector}</span>}
          {(j.required_skills || []).slice(0, 3).map((s) => (
            <span className="opps-tag" key={s.name}>{s.name}</span>
          ))}
          {(j.required_skills || []).length > 3 && (
            <span className="opps-tag opps-tag-src">
              +{j.required_skills.length - 3}
            </span>
          )}
          {j.match_score != null && (
            <span className={`opps-tag opps-tag-${scoreClass(j.match_score)}`}>
              {LEVEL_LABELS[scoreLevel(j.match_score)]}
            </span>
          )}
          <span className="opps-tag opps-tag-src">Source : {j.source.name}</span>
        </span>
      </span>
    </>
  );
}

export default function Opportunities() {
  const [params] = useSearchParams();
  // Mode « choisir une offre » : venu de la page Documents, chaque offre
  // propose directement l'adaptation (la galerie s'ouvre pour l'offre).
  const chooseMode = params.get("choisir") === "cv" || params.get("choisir") === "lettre"
    ? params.get("choisir") : null;
  const [dash, setDash] = useState(undefined);
  const [jobs, setJobs] = useState(null);
  const [careers, setCareers] = useState([]);
  const [best, setBest] = useState(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("all");
  const [sort, setSort] = useState("pertinence");
  // Pagination de la liste : 20 offres par défaut, 50 ou 100 au choix.
  const [pageSize, setPageSize] = useState(20);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({
    search: params.get("search") || "",
    sector: "",
    domain_id: "",
    specialty_id: "",
    location: "",
    contract_type: "",
  });
  const { domains } = useDomains();

  useEffect(() => {
    api("/dashboard").then(setDash).catch(() => setDash(null));
    api("/jobs?limit=200")
      .then((list) => setJobs(list || []))
      .catch((e) => setError(e.detail));
    api("/careers").then((list) => setCareers(list || [])).catch(() => setCareers([]));
  }, []);

  // La recherche du haut de page met à jour le filtre « recherche ».
  useEffect(() => {
    const s = params.get("search");
    if (s != null) setFilters((f) => ({ ...f, search: s }));
  }, [params]);

  // Offre la mieux notée : support de la carte « Votre meilleure opportunité ».
  const bestId = useMemo(() => {
    const scored = (jobs || []).filter((j) => j.match_score != null);
    if (!scored.length) return null;
    return scored.reduce((a, b) => (b.match_score > a.match_score ? b : a)).id;
  }, [jobs]);

  // Détail de la meilleure offre : compétences couvertes, partielles, manquantes.
  useEffect(() => {
    if (!bestId) {
      setBest(null);
      return;
    }
    api(`/jobs/${bestId}`).then(setBest).catch(() => setBest(null));
  }, [bestId]);

  const setFilter = (k, v) => setFilters((f) => ({ ...f, [k]: v }));
  const selectedDomain = domains.find(
    (domain) => String(domain.id) === String(filters.domain_id),
  );

  const sectors = useMemo(
    () => [...new Set((jobs || []).map((j) => j.sector).filter(Boolean))].sort(),
    [jobs]
  );
  const locations = useMemo(
    () => [...new Set((jobs || []).map((j) => j.location).filter(Boolean))].sort(),
    [jobs]
  );

  const filtered = useMemo(() => {
    const q = filters.search.trim().toLowerCase();
    return (jobs || []).filter((j) => {
      if (q && !`${j.title} ${j.company} ${j.sector}`.toLowerCase().includes(q)) return false;
      if (filters.sector && j.sector !== filters.sector) return false;
      if (filters.domain_id && String(j.domain_id) !== String(filters.domain_id)) return false;
      if (filters.specialty_id && String(j.specialty_id) !== String(filters.specialty_id)) return false;
      if (filters.location && j.location !== filters.location) return false;
      if (filters.contract_type && j.contract_type !== filters.contract_type) return false;
      return true;
    });
  }, [jobs, filters]);

  // Onglets de correspondance et tri, calculés sur les offres filtrées.
  const counts = useMemo(() => {
    const c = { all: filtered.length, forte: 0, moyenne: 0, faible: 0 };
    filtered.forEach((j) => {
      const level = scoreLevel(j.match_score);
      if (level) c[level] += 1;
    });
    return c;
  }, [filtered]);

  const visible = useMemo(() => {
    const list =
      tab === "all" ? filtered : filtered.filter((j) => scoreLevel(j.match_score) === tab);
    const sorted = [...list];
    if (sort === "recence") {
      sorted.sort((a, b) => new Date(b.published_at) - new Date(a.published_at));
    } else {
      sorted.sort((a, b) => (b.match_score ?? -1) - (a.match_score ?? -1));
    }
    return sorted;
  }, [filtered, tab, sort]);

  // Toute modification de filtre, d'onglet, de tri ou de taille de page
  // ramène à la première page (on ne reste jamais sur une page vide).
  useEffect(() => { setPage(1); }, [filters, tab, sort, pageSize]);

  const pageCount = Math.max(1, Math.ceil(visible.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const pageStart = (safePage - 1) * pageSize;
  const pageItems = visible.slice(pageStart, pageStart + pageSize);

  if (error) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!jobs || dash === undefined) {
    return <div className="page"><Loader /></div>;
  }

  const firstName = (dash?.name || "").split(" ")[0];
  const job = best?.job || null;
  const match = best?.match || null;
  const comp = dash?.profile_completeness || null;
  const trends = (dash?.market_trends || []).filter((t) => t.pct_change > 0);
  const topTrend = [...trends].sort((a, b) => b.pct_change - a.pct_change)[0];
  const week = dash?.market_week || null;
  const coveredCount = match ? match.covered.length : 0;
  const totalSkills = match ? match.covered.length + match.partial.length + match.missing.length : 0;
  const coverage = totalSkills ? Math.round((coveredCount / totalSkills) * 100) : 0;
  const strongest = filtered.filter((j) => scoreLevel(j.match_score) === "forte").length;
  const reachable = filtered.filter((j) => scoreLevel(j.match_score) === "moyenne").length;
  const topCareers = [...careers]
    .sort((a, b) => (b.match?.score ?? 0) - (a.match?.score ?? 0))
    .slice(0, 3);
  const scored = (jobs || []).some((j) => j.match_score != null);

  return (
    <div className="page opps-page">
      <div className="dash-columns">
        <div className="dash-col-main">
          {/* ---------- Bandeau ---------- */}
          <section className="home-hero opps-hero">
            <h1>Bonjour {firstName || "à vous"}</h1>
            <p className="opps-hero-lead">Voici les opportunités qui correspondent à votre profil.</p>
            <p className="opps-hero-note">
              {scored
                ? `Nous avons analysé votre profil et identifié ${jobs.length} opportunité${plural(jobs.length, "", "s")} adaptée${plural(jobs.length, "", "s")} à vos compétences et à vos objectifs.`
                : `Nous avons identifié ${jobs.length} opportunité${plural(jobs.length, "", "s")} sur le marché. Complétez votre profil pour connaître votre correspondance avec chacune d'elles.`}
            </p>
          </section>

          {/* ---------- Trois indicateurs réels ---------- */}
          <div className="opps-stats">
            <div className="opps-stat opps-stat-green">
              <span className="opps-stat-icon"><Icon d={I.target} size={18} /></span>
              <span className="opps-stat-num">{strongest}</span>
              <span className="opps-stat-label">
                opportunité{plural(strongest, "", "s")} prioritaire{plural(strongest, "", "s")}
              </span>
              <span className="opps-stat-note">Correspondance forte (≥ 75 sur 100)</span>
            </div>
            <div className="opps-stat opps-stat-blue">
              <span className="opps-stat-icon"><Icon d={I.zap} size={18} /></span>
              <span className="opps-stat-num">{reachable}</span>
              <span className="opps-stat-label">
                opportunité{plural(reachable, "", "s")} accessible{plural(reachable, "", "s")}
              </span>
              <span className="opps-stat-note">Avec une montée en compétences</span>
            </div>
            <div className="opps-stat opps-stat-violet">
              <span className="opps-stat-icon"><Icon d={I.chart} size={18} /></span>
              <span className="opps-stat-num">{week ? week.offers_in_period : 0}</span>
              <span className="opps-stat-label">nouvelle{plural(week?.offers_in_period || 0, "", "s")} offre{plural(week?.offers_in_period || 0, "", "s")} cette semaine</span>
              <span className="opps-stat-note">
                {topTrend
                  ? `+${topTrend.pct_change} % sur ${topTrend.name}`
                  : week?.period_label || "Sur la période en cours"}
              </span>
            </div>
          </div>

          {/* ---------- Votre meilleure opportunité ---------- */}
          {job ? (
            <section className="opps-best">
              <div className="opps-best-head">
                <Icon d={I.rocket} size={17} />
                <h2>Votre meilleure opportunité</h2>
                {match && (
                  <span className="badge badge-strong">
                    {LEVEL_LABELS[scoreLevel(match.score)]} correspondance
                  </span>
                )}
              </div>

              <div className="opps-best-top">
                <div className="opps-best-media">
                  <span className="opps-best-logo">{initialsOf(job.company)}</span>
                  <span className="opps-best-company">{job.company}</span>
                </div>
                <div className="opps-best-id">
                  <div className="opps-best-title-row">
                    <h3>{job.title}</h3>
                    {job.match_score != null && (
                      <span className={`opps-score opps-score-${scoreClass(job.match_score)}`}>
                        {job.match_score}/100
                      </span>
                    )}
                  </div>
                  <div className="opps-best-meta">
                    <span><Icon d={I.briefcase} size={13} /> {job.company}</span>
                    <span><Icon d={I.pin} size={13} /> {job.location}</span>
                    <span><Icon d={I.clipboard} size={13} /> {job.contract_type}</span>
                    <span><Icon d={I.clock} size={13} /> {publishedLabel(job.published_at)}</span>
                  </div>
                  <p className="opps-best-desc">
                    {(job.description || "").split("\n").filter(Boolean)[0] || job.requirements || ""}
                  </p>
                  <p className="opps-best-source small">
                    Source :{" "}
                    <a href={job.source.url} target="_blank" rel="noreferrer">{job.source.name}</a>
                    {job.sector ? ` · ${job.sector}` : ""}
                  </p>
                </div>
              </div>

              {match && (
                <div className="opps-best-grid">
                  <div className="opps-panel">
                    <div className="opps-panel-head">
                      <h4>Pourquoi cette offre vous correspond ?</h4>
                    </div>
                    <p className="opps-panel-note">
                      {coveredCount}/{totalSkills} compétence{plural(totalSkills, "", "s")} correspondent
                    </p>
                    <span className="score-bar-track">
                      <span className="score-bar-fill fill-green" style={{ width: `${coverage}%` }} />
                    </span>
                    <p className="opps-panel-text">{match.explanation}</p>
                  </div>

                  <div className="opps-panel">
                    <div className="opps-panel-head"><h4>Vos points forts</h4></div>
                    {match.covered.length > 0 ? (
                      <ul className="opps-marks">
                        <MatchMarks covered={match.covered.slice(0, 6)} />
                      </ul>
                    ) : (
                      <p className="opps-panel-text muted">
                        Aucune compétence couverte pour l'instant.
                      </p>
                    )}
                  </div>

                  <div className="opps-panel">
                    <div className="opps-panel-head"><h4>À renforcer</h4></div>
                    {match.partial.length + match.missing.length > 0 ? (
                      <ul className="opps-marks">
                        <MatchMarks
                          partial={match.partial.slice(0, 4)}
                          missing={match.missing.slice(0, 4)}
                        />
                      </ul>
                    ) : (
                      <p className="opps-panel-text muted">
                        Toutes les compétences requises sont couvertes.
                      </p>
                    )}
                  </div>
                </div>
              )}

              <div className="opps-best-actions">
                <Link className="btn btn-primary" to={`/opportunites/${job.id}`}>
                  Voir l'offre complète <ArrowIcon direction="right" size={13} />
                </Link>
                <Link className="btn btn-outline" to={`/opportunites/${job.id}?galerie=cv`}>
                  Adapter mon CV
                </Link>
                <Link className="btn btn-ghost" to="/candidatures">
                  Suivre mes candidatures
                </Link>
              </div>
            </section>
          ) : (
            <section className="opps-best opps-best-empty">
              <div className="opps-best-head">
                <Icon d={I.rocket} size={17} />
                <h2>Votre meilleure opportunité</h2>
              </div>
              <p className="muted">
                Complétez votre profil pour connaître la correspondance avec chaque offre
                et voir apparaître ici votre meilleure piste.
              </p>
              <Link className="btn btn-primary" to="/onboarding">
                Construire mon profil <ArrowIcon direction="right" size={13} />
              </Link>
            </section>
          )}

          {/* ---------- Toutes les opportunités ---------- */}
          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.target} size={16} /> Toutes les opportunités pour vous</h2>
              <label className="opps-sort">
                <span>Trier par</span>
                <select value={sort} onChange={(e) => setSort(e.target.value)}>
                  <option value="pertinence">Pertinence</option>
                  <option value="recence">Récence</option>
                </select>
              </label>
            </div>

            {scored && (
              <div className="opps-tabs" role="tablist">
                {TABS.map((t) => (
                  <button
                    key={t.key}
                    type="button"
                    role="tab"
                    aria-selected={tab === t.key}
                    className={`opps-tab${tab === t.key ? " is-active" : ""}`}
                    onClick={() => setTab(t.key)}
                  >
                    {t.label} ({counts[t.key]})
                  </button>
                ))}
              </div>
            )}

            <div className="opps-filters">
              <label className="opps-search">
                <Icon d={I.search} size={15} />
                <input
                  value={filters.search}
                  onChange={(e) => setFilter("search", e.target.value)}
                  placeholder="Métier, entreprise, mot-clé…"
                  aria-label="Rechercher une offre"
                />
              </label>
              <label className="field">
                <span>Domaine</span>
                <select
                  value={filters.domain_id}
                  onChange={(e) => {
                    setFilter("domain_id", e.target.value);
                    setFilter("specialty_id", "");
                  }}
                >
                  <option value="">Tous</option>
                  {domains.map((domain) => (
                    <option key={domain.id} value={domain.id}>{domain.name}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Spécialité</span>
                <select
                  value={filters.specialty_id}
                  onChange={(e) => setFilter("specialty_id", e.target.value)}
                  disabled={!selectedDomain}
                >
                  <option value="">Toutes</option>
                  {(selectedDomain?.specialties || []).map((specialty) => (
                    <option key={specialty.id} value={specialty.id}>{specialty.name}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Secteur (libre)</span>
                <select value={filters.sector} onChange={(e) => setFilter("sector", e.target.value)}>
                  <option value="">Tous</option>
                  {sectors.map((s) => <option key={s}>{s}</option>)}
                </select>
              </label>
              <label className="field">
                <span>Localisation</span>
                <select value={filters.location} onChange={(e) => setFilter("location", e.target.value)}>
                  <option value="">Toutes</option>
                  {locations.map((l) => <option key={l}>{l}</option>)}
                </select>
              </label>
              <label className="field">
                <span>Contrat</span>
                <select
                  value={filters.contract_type}
                  onChange={(e) => setFilter("contract_type", e.target.value)}
                >
                  <option value="">Tous</option>
                  {CONTRACT_TYPES.map((c) => <option key={c}>{c}</option>)}
                </select>
              </label>
            </div>

            {!scored && (
              <div className="alert alert-info">
                Complétez votre profil pour voir votre correspondance avec chaque offre.{" "}
                <Link to="/onboarding">Construire mon profil →</Link>
              </div>
            )}

            {visible.length === 0 ? (
              <p className="small muted opps-none">
                Aucune offre ne correspond à ces critères. Élargissez votre recherche
                ou revenez plus tard : de nouvelles opportunités sont ajoutées régulièrement.
              </p>
            ) : (
              <div className="opps-list">
                {chooseMode && (
                  <div className="opps-choose-banner">
                    <Icon d={I.compass} size={16} />
                    <div>
                      <strong>
                        {chooseMode === "cv"
                          ? "Vous adaptez votre CV : choisissez l'offre"
                          : "Vous adaptez votre lettre : choisissez l'offre"}
                      </strong>
                      <p>
                        La galerie des modèles s'ouvrira directement pour
                        l'offre choisie, puis le PDF part en téléchargement.
                      </p>
                    </div>
                  </div>
                )}
                {pageItems.map((j) => chooseMode ? (
                  <div className="opps-row opps-row-choose" key={j.id}>
                    <Link className="opps-row-grow" to={`/opportunites/${j.id}`}>
                      <OppRowMain j={j} domains={domains} />
                    </Link>
                    <Link
                      className="btn btn-primary btn-small opps-row-btn"
                      to={`/opportunites/${j.id}?galerie=${chooseMode}`}
                    >
                      {chooseMode === "cv" ? "Adapter mon CV" : "Adapter ma lettre"}
                      <ArrowIcon direction="right" size={12} />
                    </Link>
                  </div>
                ) : (
                  <Link className="opps-row" to={`/opportunites/${j.id}`} key={j.id}>
                    <OppRowMain j={j} domains={domains} />
                    <span className="btn btn-primary btn-small opps-row-btn">
                      Voir l'offre <ArrowIcon direction="right" size={12} />
                    </span>
                  </Link>
                ))}
              </div>
            )}

            {visible.length > 0 && (
              <div className="opps-pagination">
                <label className="opps-page-size">
                  <span>Offres par page</span>
                  <select
                    value={pageSize}
                    onChange={(e) => setPageSize(Number(e.target.value))}
                  >
                    <option value={20}>20</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </select>
                </label>
                <div className="opps-page-nav">
                  <button
                    type="button"
                    className="btn btn-outline btn-small"
                    disabled={safePage <= 1}
                    onClick={() => setPage(safePage - 1)}
                  >
                    Précédent
                  </button>
                  <span className="opps-page-info">
                    {pageStart + 1} à {Math.min(pageStart + pageSize, visible.length)} sur{" "}
                    {visible.length} offre{plural(visible.length, "", "s")} · page {safePage} sur {pageCount}
                  </span>
                  <button
                    type="button"
                    className="btn btn-outline btn-small"
                    disabled={safePage >= pageCount}
                    onClick={() => setPage(safePage + 1)}
                  >
                    Suivant
                  </button>
                </div>
              </div>
            )}
          </section>

          {/* ---------- Recherche infructueuse ---------- */}
          <section className="opps-alert">
            <span className="opps-alert-icon"><Icon d={I.search} size={19} /></span>
            <div>
              <h3>Vous ne trouvez pas ce que vous cherchez ?</h3>
              <p>
                Décrivez votre projet à l'assistant IA : il vous proposera des
                métiers proches de votre profil et les compétences à renforcer.
              </p>
            </div>
            <Link className="btn btn-outline" to="/agent">
              Demander à l'assistant <ArrowIcon direction="right" size={12} />
            </Link>
          </section>
        </div>

        {/* ---------- Colonne latérale ---------- */}
        <div className="dash-col-side">
          <AgentSideCard
            page="Offres"
            hint="Ori peut cibler les offres qui collent vraiment à votre profil et expliquer chaque écart."
          />
          {comp && (
            <section className="dash-card opps-profile">
              <div className="dash-card-head">
                <h2>Votre profil</h2>
                <Link className="link-more" to="/profil">
                  Détail <ArrowIcon direction="right" />
                </Link>
              </div>
              <div className="opps-profile-body">
                <Ring score={comp.score} text={`${comp.score}%`} />
                <div>
                  <strong>Force du profil</strong>
                  <p className="small muted">
                    {comp.missing.length > 0
                      ? `${comp.missing.length} élément${plural(comp.missing.length, "", "s")} à compléter pour être plus visible.`
                      : "Votre profil est complet : les recruteurs peuvent vous contacter."}
                  </p>
                </div>
              </div>
              <Link className="btn btn-primary btn-small opps-profile-btn" to="/profil">
                Améliorer mon profil <ArrowIcon direction="right" size={12} />
              </Link>
            </section>
          )}

          {trends.length > 0 && (
            <section className="dash-card">
              <div className="dash-card-head">
                <h2>Tendances du marché</h2>
                <Link className="link-more" to="/carriere">
                  Voir plus <ArrowIcon direction="right" />
                </Link>
              </div>
              <p className="small muted" style={{ marginTop: 0 }}>
                Compétences en forte demande cette semaine.
              </p>
              <ul className="opps-trends">
                {[...trends].sort((a, b) => b.pct_change - a.pct_change).slice(0, 4).map((t) => (
                  <li key={t.name}>
                    <span>
                      {t.name}
                      <br />
                      <span className="count">
                        {t.offers} offre{plural(t.offers, "", "s")} cette semaine
                      </span>
                    </span>
                    <span className="up">+{t.pct_change} %</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {topCareers.length > 0 && (
            <section className="potentiel-card">
              <div className="potentiel-head">
                <Icon d={I.compass} size={18} />
                <div>
                  <h2>Votre potentiel</h2>
                  <p>
                    {topCareers.length} trajectoire{plural(topCareers.length, "", "s")} professionnelle
                    {plural(topCareers.length, "", "s")} à votre portée
                  </p>
                </div>
                <Link to="/carriere" aria-label="Voir toutes les trajectoires">
                  <ArrowIcon direction="right" size={14} />
                </Link>
              </div>
              <ul className="potentiel-list">
                {topCareers.map((c) => (
                  <li key={c.id}>
                    <Link to={`/carriere?career=${c.id}`}>
                      <span className="potentiel-title">{c.title}</span>
                      <span className="potentiel-score">{c.match?.score}%</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {(dash?.ai_briefing || topTrend) && (
            <section className="advice-card">
              <span className="journey-icon green"><Icon d={I.lightbulb} size={17} /></span>
              <div>
                <h3>Conseil du jour</h3>
                <p>
                  {dash?.ai_briefing ||
                    `Les compétences en ${topTrend.name} sont très recherchées cette semaine. Renforcez-les pour élargir vos opportunités.`}
                </p>
                <Link className="btn btn-outline btn-small" to="/learning">
                  Voir mon plan d'amélioration <ArrowIcon direction="right" size={12} />
                </Link>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
