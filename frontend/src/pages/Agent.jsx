import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { Icon, I, ArrowIcon } from "../components/icons.jsx";
import { Loader, ErrorNote } from "../components/ui.jsx";
import Ring from "../components/Ring.jsx";
import AssistantChat from "../components/AssistantChat.jsx";
import AgentHistoryControls from "../components/AgentHistoryControls.jsx";
import { initialsOf, mapInternalPath, plural, relTime, scoreLevel, LEVEL_LABELS } from "../lib.js";

// Page « Mon agent » (maquette) : poste de pilotage où l'agent travaille
// POUR le jeune : héros, étapes réelles, statistiques, action requise,
// opportunités récentes, et barre de commande de l'assistant.
// Toutes les valeurs proviennent de l'API (§47) : aucune donnée inventée.

const KIND_ICONS = {
  new_job: I.briefcase,
  strong_match: I.target,
  trend: I.trending,
  learning: I.book,
  application: I.file,
};

const AGENT_MODES = [
  { id: "accompagnement", label: "Mode accompagnement", description: "Je recommande et j'alerte sur les opportunités pertinentes.", icon: I.shield },
  { id: "preparation", label: "Mode préparation", description: "Je prépare les CV et lettres ciblés ; vous validez chaque envoi.", icon: I.bot },
  { id: "veille", label: "Mode veille", description: "Je surveille les nouvelles offres de votre domaine et je vous informe.", icon: I.search },
  { id: "autonome", label: "Mode autonome", description: "Je prépare automatiquement les documents pour vos meilleures correspondances ; vous validez l'envoi.", icon: I.spark },
];

function nextActionHref(action) {
  if (!action) return "/";
  if (action.href) return mapInternalPath(action.href);
  if (action.type === "review_application") return "/candidatures";
  if (action.type === "build_profile") return "/onboarding";
  if (action.type === "learn") return "/learning";
  if (action.job_id) return `/opportunites/${action.job_id}`;
  return "/opportunites";
}

function scoreClass(score) {
  if (score >= 75) return "strong";
  if (score >= 45) return "medium";
  return "weak";
}

export default function Agent() {
  const [data, setData] = useState(null);
  const [profile, setProfile] = useState(undefined);
  const [jobs, setJobs] = useState([]);
  const [applications, setApplications] = useState([]);
  const [events, setEvents] = useState([]);
  const [best, setBest] = useState(null);
  const [details, setDetails] = useState({});
  const [tab, setTab] = useState("reco");
  const [showStrengths, setShowStrengths] = useState(true);
  const [error, setError] = useState("");
  const [agentMode, setAgentMode] = useState("preparation");
  const [modes, setModes] = useState(AGENT_MODES);
  const [modeBusy, setModeBusy] = useState(false);
  const [modeFlash, setModeFlash] = useState("");
  const [modeError, setModeError] = useState("");

  useEffect(() => {
    api("/dashboard").then(setData).catch((e) => setError(e.detail));
    api("/profile").then(setProfile).catch(() => setProfile(null));
    api("/jobs?min_score=45").then((j) => setJobs(j || [])).catch(() => setJobs([]));
    api("/applications").then((a) => setApplications(a || [])).catch(() => setApplications([]));
    api("/notifications").then((e) => setEvents(e || [])).catch(() => setEvents([]));
    api("/agent/mode")
      .then((res) => {
        setAgentMode(res.mode);
        const icons = Object.fromEntries(AGENT_MODES.map((m) => [m.id, m.icon]));
        setModes((res.modes || []).map((m) => ({
          ...m,
          icon: icons[m.id] || I.bot,
        })));
      })
      .catch(() => {});
  }, []);

  async function chooseMode(mode) {
    if (mode === agentMode || modeBusy) return;
    setModeBusy(true);
    setModeError("");
    setModeFlash("");
    try {
      const res = await api("/agent/mode", { method: "PUT", body: { mode } });
      setAgentMode(res.mode);
      setModeFlash("Mode enregistré. L'agent s'adapte dès maintenant.");
    } catch (err) {
      setModeError(err.detail);
    } finally {
      setModeBusy(false);
    }
  }

  // Meilleure piste : score + compétences couvertes / manquantes.
  useEffect(() => {
    if (!data) return;
    const id = data.next_action?.job_id || data.top_matches?.[0]?.id;
    if (!id) return;
    api(`/jobs/${id}`).then(setBest).catch(() => setBest(null));
  }, [data]);

  const byTab = {
    reco: jobs.filter((j) => j.match_score != null && j.match_score >= 75),
    portee: jobs.filter((j) => j.match_score != null && j.match_score >= 45 && j.match_score < 75),
    toutes: jobs,
  };
  const list = (byTab[tab] || []).slice(0, 4);
  const visibleKey = list.map((j) => j.id).join(",");

  // Détail des offres affichées (compétences requises + couverture réelle).
  useEffect(() => {
    if (!visibleKey) return;
    const ids = visibleKey
      .split(",")
      .map(Number)
      .filter((id) => !details[id]);
    if (!ids.length) return;
    let alive = true;
    Promise.all(
      ids.map((id) => api(`/jobs/${id}`).then((d) => ({ id, d })).catch(() => null))
    ).then((res) => {
      if (!alive) return;
      setDetails((prev) => {
        const next = { ...prev };
        res.filter(Boolean).forEach((r) => { next[r.id] = r.d; });
        return next;
      });
    });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleKey]);

  if (error) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!data || profile === undefined) {
    return <div className="page"><Loader /></div>;
  }

  const firstName = (data.name || "").split(" ")[0];
  const skillsCount = profile?.skills?.length || 0;
  const pending = applications.filter((a) => a.status === "cv_prepare");
  const preparedCount = pending.length;

  // ---- Profil absent : inviter à démarrer ----
  if (profile === null) {
    return (
      <div className="page agent-page">
        <section className="ag-hero">
          <span className="ag-hero-mascot"><Icon d={I.bot} size={44} /></span>
          <div className="ag-hero-body">
            <div className="ag-hero-top">
              <h1>Mon agent</h1>
              <span className="agent-status">En attente de votre profil</span>
            </div>
            <p className="ag-hero-tagline">Votre agent carrière travaille pour vous</p>
            <p className="ag-hero-desc">{data.ai_briefing}</p>
            <div className="ag-hero-foot">
              <Link className="btn btn-primary btn-small" to="/onboarding">Importer mon CV</Link>
              <Link className="btn btn-ghost btn-small" to="/questionnaire">Créer mon profil</Link>
            </div>
          </div>
        </section>
      </div>
    );
  }

  const steps = [
    { n: 1, label: "Rechercher", sub: "Nouvelles offres sur plusieurs sources", icon: I.search, done: data.new_opportunities > 0 },
    { n: 2, label: "Analyser", sub: "Le marché et les tendances", icon: I.chart, done: data.market_week.offers_in_period > 0 },
    { n: 3, label: "Matcher", sub: "Avec votre profil et vos objectifs", icon: I.target, done: data.strong_matches > 0 },
    { n: 4, label: "Préparer", sub: "Les candidatures ciblées", icon: I.clipboard, done: preparedCount > 0 },
    { n: 5, label: "Vous notifier", sub: "Des opportunités pertinentes", icon: I.bell, done: data.interviews_to_prepare > 0 },
  ];
  const doneCount = steps.filter((s) => s.done).length;

  const prev = data.market_week.previous_period_offers;
  const weekDelta = prev > 0
    ? Math.round(((data.market_week.offers_in_period - prev) / prev) * 100)
    : null;

  const stats = [
    { icon: I.search, value: data.market_week.offers_in_period, label: "Opportunités trouvées", note: "cette semaine", delta: weekDelta },
    { icon: I.target, value: data.strong_matches, label: "Opportunités pertinentes", note: "pour votre profil", delta: null },
    { icon: I.clipboard, value: preparedCount, label: "Candidatures préparées", note: "prêtes à votre approbation", delta: null },
    { icon: I.file, value: skillsCount, label: "Compétences analysées", note: "dans votre profil", delta: null },
  ];

  const focus = pending[0] || applications.filter((a) => a.status === "entretien")[0] || applications[0] || null;
  const focusJob = focus?.job || null;
  const focusScore = focusJob
    ? focusJob.match_score ?? jobs.find((j) => j.id === focusJob.id)?.match_score ?? null
    : null;
  const focusNeedsAction = focus ? ["cv_prepare", "entretien"].includes(focus.status) : false;
  const otherPending = focus && focus.status === "cv_prepare" ? pending.length - 1 : pending.length;
  const hasCv = (focus?.documents || []).some((d) => d.kind === "cv");
  const hasLetter = (focus?.documents || []).some((d) => d.kind === "cover_letter");

  const bestJob = best?.job || null;
  const bestMatch = best?.match || null;
  const coverageTotal = bestMatch
    ? bestMatch.covered.length + bestMatch.partial.length + bestMatch.missing.length
    : 0;

  const tabs = [
    { id: "reco", label: "Recommandées" },
    { id: "portee", label: "À votre portée" },
    { id: "toutes", label: "Toutes" },
  ];

  return (
    <div className="page agent-page">
      <div className="dash-columns">
        <div className="dash-col-main">
          {/* ---------- Héros « Mon agent » ---------- */}
          <div className="ag-hero-wrap">
          <section className="ag-hero">
            <span className="ag-hero-mascot"><Icon d={I.bot} size={44} /></span>
            <div className="ag-hero-body">
              <div className="ag-hero-top">
                <h1>Mon agent</h1>
                <span className="agent-status">Actif</span>
              </div>
              <p className="ag-hero-tagline">
                {data.ai_label || "Votre agent carrière travaille pour vous"}
              </p>
              <p className="ag-hero-desc">
                {data.ai_briefing}
              </p>
              <div className="ag-hero-foot">
                {events[0] && (
                  <span className="ag-hero-last">
                    Dernière activité : {relTime(events[0].at)}
                  </span>
                )}
                <Link className="btn btn-outline btn-small" to="/assistant">
                  Discuter avec l'agent <ArrowIcon direction="right" size={13} />
                </Link>
                <Link className="btn btn-ghost btn-small" to="/notifications">
                  Voir le détail de l'activité <ArrowIcon direction="right" size={13} />
                </Link>
              </div>
            </div>
            <aside className="ag-quote">
              <Icon d={I.spark} size={18} />
              <p>« Je recherche, j'analyse, je prépare. Vous décidez. »</p>
            </aside>
          </section>
          </div>

          {/* ---------- Prochaine action recommandée ---------- */}
          {data.next_action && (
            <section className="ag-next-action">
              <span className="ag-next-icon"><Icon d={I.target} size={20} /></span>
              <div className="ag-next-main">
                <span className="ag-next-eyebrow">Recommandation immédiate</span>
                <h2>{data.next_action.label}</h2>
                <p>
                  L'agent a calculé cette priorité à partir de votre profil, de
                  vos candidatures et des offres réelles. Vous gardez la décision.
                </p>
              </div>
              <Link className="btn btn-primary" to={nextActionHref(data.next_action)}>
                Faire cette action <ArrowIcon direction="right" size={12} />
              </Link>
            </section>
          )}

          {/* ---------- Étapes en cours ---------- */}
          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.gear} size={16} /> En ce moment, mon agent travaille sur…</h2>
            </div>
            <div className="ag-steps">
              {steps.map((s) => (
                <div key={s.n} className={`ag-step${s.done ? " done" : ""}`}>
                  <span className="ag-step-num">{s.n}</span>
                  <span className="ag-step-icon"><Icon d={s.icon} size={16} /></span>
                  <span className={`ag-step-state${s.done ? " done" : " pending"}`}>
                    {s.done ? <Icon d={I.check} size={14} /> : null}
                  </span>
                  <span className="ag-step-label">{s.label}</span>
                  <span className="ag-step-sub">{s.sub}</span>
                </div>
              ))}
            </div>
            <div className="ag-progress">
              <span className="ag-progress-icon"><Icon d={I.activity} size={15} /></span>
              <span className="ag-progress-text">
                Progression de votre agent : {doneCount} étape{plural(doneCount, "", "s")} sur {steps.length}
              </span>
              <span className="ag-progress-track">
                <span className="ag-progress-fill" style={{ width: `${(doneCount / steps.length) * 100}%` }} />
              </span>
              <span className="ag-progress-pct">{Math.round((doneCount / steps.length) * 100)} %</span>
            </div>
          </section>

          {/* ---------- Statistiques ---------- */}
          <section className="ag-stats">
            {stats.map((s) => (
              <div key={s.label} className="ag-stat">
                <div className="ag-stat-head">
                  <span className="ag-stat-icon"><Icon d={s.icon} size={16} /></span>
                  <span className="ag-stat-label">{s.label}</span>
                </div>
                <div className="ag-stat-value">{s.value}</div>
                <div className="ag-stat-foot">
                  <span className="ag-stat-note">{s.note}</span>
                  {s.delta != null && (
                    <span className={`ag-stat-delta${s.delta < 0 ? " down" : ""}`}>
                      {s.delta >= 0 ? <ArrowIcon direction="up" size={12} /> : <ArrowIcon direction="down" size={12} />}
                      {s.delta > 0 ? "+" : ""}{s.delta} %
                    </span>
                  )}
                </div>
              </div>
            ))}
          </section>

          {/* ---------- À votre attention ---------- */}
          <section className="ag-attn">
            <div className="ag-attn-head">
              <h2><Icon d={I.target} size={16} /> À votre attention</h2>
              <span className="ag-attn-tag">
                {focusNeedsAction ? "Action requise" : "À découvrir"}
              </span>
              <Link className="link-more" to="/candidatures">
                Voir toutes <ArrowIcon direction="right" />
              </Link>
            </div>

            {focusJob ? (
              <>
                <div className="ag-attn-row">
                  {focusScore != null && (
                    <span className="ag-attn-score">
                      <span className="ag-attn-score-label">Match</span>
                      <strong>{focusScore}%</strong>
                    </span>
                  )}
                  <span className="opp-logo">{initialsOf(focusJob.company)}</span>
                  <span className="ag-attn-main">
                    <span className="ag-attn-title">{focusJob.title}</span>
                    <span className="opp-meta">
                      {focusJob.company} · {focusJob.location} · {focusJob.contract_type}
                    </span>
                    <span className="ag-attn-chip">
                      <Icon d={I.check} size={12} /> {STATUS_HINT[focus.status] || "Candidature en cours"}
                    </span>
                  </span>
                  <span className="ag-attn-actions">
                    <Link className="btn btn-primary btn-small" to="/candidatures">
                      Revoir la candidature <ArrowIcon direction="right" size={12} />
                    </Link>
                    <Link className="btn btn-outline btn-small" to={`/opportunites/${focusJob.id}`}>
                      Voir le détail
                    </Link>
                  </span>
                </div>
                {(hasCv || hasLetter) && (
                  <div className="ag-attn-meta">
                    {hasCv && <span><Icon d={I.check} size={13} /> CV adapté</span>}
                    {hasLetter && <span><Icon d={I.check} size={13} /> Lettre de motivation</span>}
                  </div>
                )}
                {otherPending > 0 && (
                  <p className="ag-attn-foot">
                    <Icon d={I.spark} size={13} /> {otherPending} autre{plural(otherPending, "", "s")} candidature{plural(otherPending, "", "s")} en attente de votre validation
                  </p>
                )}
              </>
            ) : bestJob ? (
              <div className="ag-attn-row">
                <span className="opp-logo">{initialsOf(bestJob.company)}</span>
                <span className="ag-attn-main">
                  <span className="ag-attn-title">{bestJob.title}</span>
                  <span className="opp-meta">
                    {bestJob.company} · {bestJob.location} · {bestJob.contract_type}
                  </span>
                  <span className="ag-attn-chip muted">
                    <Icon d={I.spark} size={12} /> Aucune candidature préparée pour l'instant
                  </span>
                </span>
                <span className="ag-attn-actions">
                  <Link className="btn btn-primary btn-small" to={`/opportunites/${bestJob.id}`}>
                    Voir l'offre <ArrowIcon direction="right" size={12} />
                  </Link>
                </span>
              </div>
            ) : (
              <p className="muted small">Rien à signaler pour le moment.</p>
            )}
          </section>

          {/* ---------- Opportunités récentes ---------- */}
          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.briefcase} size={16} /> Opportunités récentes</h2>
              <Link className="link-more" to="/opportunites">
                Voir toutes <ArrowIcon direction="right" />
              </Link>
            </div>
            <div className="ag-tabs" role="tablist">
              {tabs.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={tab === t.id}
                  className={`ag-tab${tab === t.id ? " active" : ""}`}
                  onClick={() => setTab(t.id)}
                >
                  {t.label} ({byTab[t.id].length})
                </button>
              ))}
            </div>
            {list.length === 0 ? (
              <p className="muted small">Aucune offre dans cette catégorie pour l'instant.</p>
            ) : (
              list.map((j) => {
                const d = details[j.id];
                const m = d?.match || null;
                const req = d?.job?.required_skills || [];
                return (
                  <div key={j.id} className="ag-row">
                    <span className={`ag-row-score ag-row-score-${scoreClass(j.match_score)}`}>
                      <b>{j.match_score}%</b>
                      <span>{LEVEL_LABELS[scoreLevel(j.match_score)]}</span>
                    </span>
                    <span className="opp-logo">{initialsOf(j.company)}</span>
                    <span className="ag-row-main">
                      <span className="ag-row-title">{j.title}</span>
                      <span className="opp-meta">
                        {j.company} · {j.location} · {j.contract_type}
                      </span>
                      {req.length > 0 && (
                        <span className="ag-row-chips">
                          {req.slice(0, 3).map((r) => (
                            <span key={r.name} className="chip chip-mini">{r.name}</span>
                          ))}
                          {req.length > 3 && (
                            <span className="chip chip-mini">+{req.length - 3}</span>
                          )}
                        </span>
                      )}
                    </span>
                    {m && (
                      <span className="ag-row-comp">
                        <span className="ag-row-cov">
                          <Icon d={I.check} size={12} /> {m.covered.length}/{req.length} compétences
                        </span>
                        {m.missing.length > 0 && (
                          <span className="ag-row-miss">
                            <Icon d={I.alert} size={12} /> {m.missing.length} à renforcer
                          </span>
                        )}
                      </span>
                    )}
                    <Link className="btn btn-primary btn-small" to={`/opportunites/${j.id}`}>
                      Voir l'offre
                    </Link>
                  </div>
                );
              })
            )}
          </section>

          {/* ---------- Votre potentiel ---------- */}
          {data.skills_to_improve.length > 0 && (
            <section className="ag-potential">
              <span className="ag-potential-icon"><Icon d={I.target} size={20} /></span>
              <div className="ag-potential-main">
                <h3>Votre potentiel est plus grand</h3>
                <p>
                  J'ai identifié {data.skills_to_improve.length} compétence{plural(data.skills_to_improve.length, "", "s")} clé{plural(data.skills_to_improve.length, "", "s")} qui
                  pourraient booster votre profil et vous ouvrir de nouvelles opportunités.
                  Je vous ai préparé un parcours de formation personnalisé.
                </p>
              </div>
              <Link
                className="btn btn-outline"
                to={data.learning_focus?.href
                  ? mapInternalPath(data.learning_focus.href)
                  : "/learning"}
              >
                Voir mon plan de progression <ArrowIcon direction="right" size={13} />
              </Link>
            </section>
          )}

          {/* ---------- Barre de commande de l'assistant ---------- */}
          <AssistantChat compact />
        </div>

        {/* ---------- Colonne latérale ---------- */}
        <div className="dash-col-side">
          {events.length > 0 && (
            <section className="dash-card">
              <div className="dash-card-head">
                <h2>Mon activité récente</h2>
                <Link className="link-more" to="/notifications">
                  Tout voir <ArrowIcon direction="right" />
                </Link>
              </div>
              <ul className="ag-activity">
                {events.slice(0, 5).map((ev) => (
                  <li key={ev.id}>
                    <span className={`ag-activity-dot kind-${ev.kind}`}>
                      <Icon d={KIND_ICONS[ev.kind] || I.activity} size={15} />
                    </span>
                    <span className="ag-activity-main">
                      <span className="ag-activity-text">{ev.message}</span>
                      <span className="ag-activity-time">
                        {relTime(ev.at)}
                        {ev.job_id && (
                          <>
                            {" · "}
                            <Link className="link-more" to={`/opportunites/${ev.job_id}`}>
                              voir l'offre
                            </Link>
                          </>
                        )}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {bestJob && bestMatch && (
            <section className="dash-card">
              <div className="dash-card-head">
                <h2><Icon d={I.check} size={16} /> Pourquoi cette offre ?</h2>
              </div>
              <div className="ag-why-head">
                <span className="opp-logo">{initialsOf(bestJob.company)}</span>
                <span className="ag-why-id">
                  <span className="ag-row-title">{bestJob.title}</span>
                  <span className="opp-meta">
                    {bestJob.company} · {bestJob.location} · {bestJob.contract_type}
                  </span>
                </span>
              </div>
              <div className="ag-why-score">
                <Ring score={bestMatch.score} text={`${bestMatch.score}%`} size={78} stroke={7} />
                <span className="ag-why-score-label">Match global</span>
              </div>
              <button
                type="button"
                className="ag-why-toggle"
                aria-expanded={showStrengths}
                onClick={() => setShowStrengths((v) => !v)}
              >
                <span>
                  <Icon d={I.award} size={14} /> Vos points forts ({bestMatch.covered.length}/{coverageTotal})
                </span>
                <ArrowIcon direction={showStrengths ? "up" : "down"} size={13} />
              </button>
              {showStrengths && bestMatch.strengths.length > 0 && (
                <ul className="ag-why-list">
                  {bestMatch.strengths.slice(0, 4).map((s) => (
                    <li key={s}><Icon d={I.check} size={13} /> {s}</li>
                  ))}
                  {bestMatch.strengths.length > 4 && (
                    <li className="ag-why-more">+{bestMatch.strengths.length - 4} autres</li>
                  )}
                </ul>
              )}
              {bestMatch.missing.length > 0 && (
                <>
                  <p className="ag-why-sub">
                    <Icon d={I.alert} size={13} /> À renforcer ({bestMatch.missing.length}/{coverageTotal})
                  </p>
                  <ul className="ag-why-list warn">
                    {bestMatch.missing.slice(0, 3).map((s) => (
                      <li key={s}><Icon d={I.alert} size={13} /> {s}</li>
                    ))}
                  </ul>
                </>
              )}
              <Link className="link-more" to={`/opportunites/${bestJob.id}`}>
                Voir l'analyse complète <ArrowIcon direction="right" />
              </Link>
            </section>
          )}

          <section className="ag-mode">
            <div className="ag-mode-head">
              <span className="ag-mode-icon"><Icon d={I.gear} size={16} /></span>
              <h2>Contrôle de votre agent</h2>
            </div>
            <p className="ag-mode-lead">Définissez comment votre agent doit travailler pour vous. Ces réglages sont enregistrés sur votre compte.</p>
            {modes.map((m) => (
              <button
                key={m.id}
                type="button"
                className={`ag-mode-opt ag-mode-button${m.id === agentMode ? " active" : ""}`}
                onClick={() => chooseMode(m.id)}
                disabled={modeBusy}
                aria-pressed={m.id === agentMode}
              >
                <span className="ag-mode-opt-icon"><Icon d={m.icon} size={15} /></span>
                <span className="ag-mode-opt-main">
                  <span className="ag-mode-opt-label">{m.label}</span>
                  <span className="ag-mode-opt-desc">{m.description || m.desc}</span>
                </span>
                {m.id === agentMode && (
                  <span className="ag-mode-check"><Icon d={I.check} size={14} /></span>
                )}
              </button>
            ))}
            <p className="ag-mode-note">
              Votre validation reste requise : l'agent prépare, vous décidez.
            </p>
            <AgentHistoryControls />
            {modeFlash && <div className="alert alert-success small">{modeFlash}</div>}
            <ErrorNote error={modeError} />
            <Link className="ag-mode-link" to="/parametres-compte">
              Gérer les paramètres <ArrowIcon direction="right" size={13} />
            </Link>
          </section>

          <section className="dash-card ag-week">
            <h2><Icon d={I.chart} size={15} /> Résumé de la semaine</h2>
            <p>
              Votre agent a analysé {data.market_week.offers_in_period} offre{plural(data.market_week.offers_in_period, "", "s")} et
              identifié {data.strong_matches} correspondance{plural(data.strong_matches, "", "s")} forte{plural(data.strong_matches, "", "s")}.
            </p>
            <Link className="btn btn-outline btn-small" to="/carriere">
              Voir le rapport complet <ArrowIcon direction="right" size={12} />
            </Link>
          </section>
        </div>
      </div>
    </div>
  );
}

// Libellé court de l'état d'une candidature (aligné sur lib.js).
const STATUS_HINT = {
  identifiee: "Offre identifiée",
  cv_prepare: "Candidature prête à être revue",
  envoyee: "Candidature envoyée",
  en_attente: "En attente de réponse",
  entretien: "Entretien à préparer",
  offre: "Offre reçue",
  acceptee: "Candidature acceptée",
  refusee: "Candidature refusée",
};
