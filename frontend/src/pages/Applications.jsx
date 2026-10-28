import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import {
  STATUS_LABELS,
  fmtDate,
  fmtDateTime,
  initialsOf,
  plural,
  statusTone,
} from "../lib.js";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";
import { Icon, I, ArrowIcon } from "../components/icons.jsx";
import AssistantChat from "../components/AssistantChat.jsx";
import AgentSideCard from "../components/AgentSideCard.jsx";

// Mes candidatures (§6, §36) : mini-ATS personnel.
//
// Chaque candidature est une carte : entreprise, étape franchie (pipeline
// identifiée → … → acceptée), documents réellement générés, historique
// daté, et actions réelles (CV ciblé, lettre, préparation d'entretien).
// Rien n'est inventé : tout vient des offres suivies et du profil validé
// (§47), et chaque étape franchie reste tracée.

// Étapes qui avancent. « refusee » est un état terminal à part : on ne
// le franchit pas, on s'y arrête (le pipeline n'a donc pas de sens).
const PIPELINE = [
  "identifiee",
  "cv_prepare",
  "envoyee",
  "en_attente",
  "entretien",
  "offre",
  "acceptee",
];
const CLOSED = ["acceptee", "refusee", "retiree", "declinee"];

const TABS = [
  { id: "toutes", label: "Toutes" },
  { id: "encours", label: "En cours" },
  { id: "entretien", label: "Entretiens" },
  { id: "cloturees", label: "Clôturées" },
];

const SORTS = [
  { id: "recent", label: "Dernière mise à jour" },
  { id: "etape", label: "Étape la plus avancée" },
  { id: "entreprise", label: "Entreprise (A → Z)" },
];

const APPS_SUGGESTIONS = [
  "Où en sont mes candidatures ?",
  "Quelles candidatures relancer ?",
  "Prépare mon entretien",
  "Quelles compétences me manquent ?",
];

function stepIndex(status) {
  if (CLOSED.includes(status)) return -1;
  return PIPELINE.indexOf(status);
}

// Actions que le candidat peut réellement déclencher. Les autres
// transitions (entretien, offre, refus) appartiennent au recruteur ou à
// l'admin : elles ne sont jamais proposées ici.
const CANDIDATE_ACTIONS = {
  identifiee: [
    { status: "cv_prepare", label: "Marquer le CV préparé", variant: "btn-primary" },
    { status: "envoyee", label: "Marquer comme envoyée", variant: "btn-outline" },
  ],
  cv_prepare: [
    { status: "envoyee", label: "Marquer comme envoyée", variant: "btn-primary" },
  ],
  offre: [
    { status: "acceptee", label: "Accepter l'offre", variant: "btn-primary" },
    { status: "declinee", label: "Décliner l'offre", variant: "btn-outline" },
  ],
};

function lastUpdate(app) {
  const times = (app.timeline || [])
    .map((event) => new Date(event.at).getTime())
    .filter((time) => !Number.isNaN(time));
  return times.length ? Math.max(...times) : 0;
}

function docLabel(kind) {
  if (kind === "cv") return "CV ciblé";
  if (kind === "cover_letter") return "Lettre de motivation";
  return "Document";
}

// ------------------------------------------------------------------ briques

function StatusPipeline({ status }) {
  const current = PIPELINE.indexOf(status);
  return (
    <ol className="apps-pipeline" aria-label="Étapes de la candidature">
      {PIPELINE.map((step, index) => {
        const state = index < current ? "done" : index === current ? "current" : "todo";
        return (
          <li className={`apps-step ${state}`} key={step}>
            <span className="apps-step-dot" />
            <span className="apps-step-label">{STATUS_LABELS[step]}</span>
          </li>
        );
      })}
    </ol>
  );
}

function PrepPanel({ prep, onClose }) {
  return (
    <div className="apps-prep">
      <div className="apps-prep-head">
        <h4>Préparation d'entretien</h4>
        <button className="btn btn-ghost btn-small" onClick={onClose}>Fermer</button>
      </div>
      <h5 className="apps-sub">Pitch professionnel</h5>
      <p className="apps-text">{prep.pitch}</p>
      {prep.likely_questions.length > 0 && (
        <>
          <h5 className="apps-sub">Questions probables</h5>
          <ul className="explain-list">
            {prep.likely_questions.map((q, i) => <li key={i}>{q}</li>)}
          </ul>
        </>
      )}
      {prep.technical.length > 0 && (
        <>
          <h5 className="apps-sub">Questions techniques</h5>
          <ul className="explain-list">
            {prep.technical.map((q, i) => <li key={i}>{q}</li>)}
          </ul>
        </>
      )}
      {prep.behavioral.length > 0 && (
        <>
          <h5 className="apps-sub">Questions comportementales</h5>
          <ul className="explain-list">
            {prep.behavioral.map((q, i) => <li key={i}>{q}</li>)}
          </ul>
        </>
      )}
      {prep.prep_tips.length > 0 && (
        <>
          <h5 className="apps-sub">Conseils</h5>
          <ul className="explain-list">
            {prep.prep_tips.map((t, i) => <li key={i}>{t}</li>)}
          </ul>
        </>
      )}
    </div>
  );
}

function ApplicationCard({ app, onStatus, busy }) {
  const navigate = useNavigate();
  const [actionError, setActionError] = useState("");
  const [action, setAction] = useState(""); // cv | lettre | entretien
  const [templates, setTemplates] = useState(undefined); // undefined | null | list
  const [prep, setPrep] = useState(null);
  const [historyOpen, setHistoryOpen] = useState(false);

  const isClosed = CLOSED.includes(app.status);
  const actions = CANDIDATE_ACTIONS[app.status] || [];
  const canWithdraw = !isClosed && app.status !== "offre";
  const tone = statusTone(app.status);

  async function generateCv(templateId) {
    setAction("cv");
    setActionError("");
    try {
      const doc = await api(`/jobs/${app.job_id}/cv`, {
        method: "POST",
        body: { template: templateId },
      });
      navigate(`/documents?open=${doc.id}`);
    } catch (err) {
      setActionError(err.detail);
      setAction("");
    }
  }

  async function openTemplates() {
    if (templates !== undefined) {
      setTemplates(undefined);
      return;
    }
    setActionError("");
    setTemplates(null);
    try {
      setTemplates(await api("/cv-templates"));
    } catch (err) {
      setActionError(err.detail);
      setTemplates(undefined);
    }
  }

  async function makeLetter() {
    setAction("lettre");
    setActionError("");
    try {
      const doc = await api(`/jobs/${app.job_id}/cover-letter`, { method: "POST" });
      navigate(`/documents?open=${doc.id}`);
    } catch (err) {
      setActionError(err.detail);
      setAction("");
    }
  }

  async function prepare() {
    if (prep) {
      setPrep(null);
      return;
    }
    setAction("entretien");
    setActionError("");
    try {
      setPrep(await api(`/jobs/${app.job_id}/interview-prep`, { method: "POST" }));
    } catch (err) {
      setActionError(err.detail);
    } finally {
      setAction("");
    }
  }

  return (
    <article className="apps-item" id={`app-${app.id}`}>
      <div className="apps-item-head">
        <span className="apps-logo">{initialsOf(app.job.company)}</span>
        <div className="apps-item-main">
          <div className="apps-item-title">
            <Link to={`/opportunites/${app.job_id}`}>{app.job.title}</Link>
            <span className={`apps-status ${tone}`}>{STATUS_LABELS[app.status]}</span>
          </div>
          <p className="opp-meta">
            {app.job.company} · {app.job.location} · {app.job.contract_type} ·
            {" "}Offre publiée le {fmtDate(app.job.published_at)}
          </p>
        </div>
        <div className="apps-item-side">
          {busy ? (
            <span className="small muted">Mise à jour…</span>
          ) : (
            <>
              {actions.map((action) => (
                <button
                  key={action.status}
                  className={`btn ${action.variant} btn-small`}
                  onClick={() => onStatus(app.id, action.status)}
                >
                  {action.label}
                </button>
              ))}
              {canWithdraw && (
                <button
                  className="btn btn-ghost btn-small"
                  onClick={() => onStatus(app.id, "retiree")}
                >
                  Retirer ma candidature
                </button>
              )}
              {isClosed && (
                <span className="small muted">Dossier clôturé</span>
              )}
            </>
          )}
        </div>
      </div>

      {isClosed && app.status !== "acceptee" ? (
        <p className="apps-closed">
          <Icon d={I.alert} size={14} />
          {app.status === "refusee" &&
            "Candidature refusée. L'historique ci-dessous garde la trace réelle du parcours : il sert pour les candidatures suivantes."}
          {app.status === "retiree" &&
            "Vous avez retiré cette candidature. L'historique ci-dessous conserve la trace de votre décision."}
          {app.status === "declinee" &&
            "Vous avez décliné cette offre. L'historique ci-dessous conserve la trace de votre décision."}
        </p>
      ) : (
        <StatusPipeline status={app.status} />
      )}

      <div className="apps-item-body">
        <div className="apps-docs">
          <span className="apps-label">Documents générés</span>
          {app.documents.length === 0 ? (
            <span className="apps-none">
              Aucun document pour l'instant : le CV ciblé et la lettre sont
              construits uniquement depuis votre profil validé.
            </span>
          ) : (
            <div className="chip-row" style={{ marginTop: 0 }}>
              {app.documents.map((doc) => (
                <Link key={doc.id} className="chip" to={`/documents?open=${doc.id}`}>
                  {docLabel(doc.kind)} : {doc.title.split(" · ").slice(1).join(" · ")}
                </Link>
              ))}
            </div>
          )}
        </div>

        <div className="apps-actions">
          <button className="btn btn-outline btn-small" onClick={openTemplates}>
            {templates === undefined ? "Générer mon CV ciblé" : "Masquer les modèles"}
          </button>
          <button className="btn btn-outline btn-small" onClick={makeLetter} disabled={action === "lettre"}>
            {action === "lettre" ? "Rédaction…" : "Lettre de motivation"}
          </button>
          <button className="btn btn-outline btn-small" onClick={prepare} disabled={action === "entretien"}>
            {action === "entretien"
              ? "Préparation…"
              : prep ? "Masquer la préparation" : "Préparer l'entretien"}
          </button>
          <Link className="btn btn-ghost btn-small" to={`/opportunites/${app.job_id}`}>
            Voir l'offre
          </Link>
        </div>
      </div>

      <ErrorNote error={actionError} />

      {templates !== undefined && (
        <div className="apps-templates">
          {templates === null ? (
            <p className="apps-none">Chargement des modèles…</p>
          ) : templates.length === 0 ? (
            <p className="apps-none">Aucun modèle disponible.</p>
          ) : (
            templates.map((template) => (
              <div className="apps-template" key={template.id}>
                <div className="apps-template-head">
                  <strong>{template.name}</strong>
                  {template.ats_friendly && <span className="badge badge-strong">ATS</span>}
                </div>
                <p>{template.description}</p>
                <button
                  className="btn btn-primary btn-small"
                  onClick={() => generateCv(template.id)}
                  disabled={action === "cv"}
                >
                  {action === "cv" ? "Génération…" : `Générer en ${template.name}`}
                </button>
              </div>
            ))
          )}
        </div>
      )}

      {prep && <PrepPanel prep={prep} onClose={() => setPrep(null)} />}

      {app.timeline.length > 0 && (
        <div className="apps-history">
          <button
            className="apps-history-toggle"
            onClick={() => setHistoryOpen((open) => !open)}
            aria-expanded={historyOpen}
          >
            Historique ({app.timeline.length} étape{plural(app.timeline.length, "", "s")})
            <ArrowIcon direction={historyOpen ? "up" : "down"} size={12} />
          </button>
          {historyOpen && (
            <ol className="apps-timeline">
              {[...app.timeline].reverse().map((event, i) => (
                <li key={i}>
                  <span className="apps-timeline-dot" />
                  <span className="apps-timeline-event">
                    {event.event}
                    {event.by && (
                      <span className="apps-timeline-by"> · par {event.by}</span>
                    )}
                    {event.reason && (
                      <span className="apps-timeline-reason">
                        Motif : {event.reason}
                      </span>
                    )}
                  </span>
                  <span className="apps-timeline-date">{fmtDateTime(event.at)}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </article>
  );
}

// --------------------------------------------------------------------- page

export default function Applications() {
  const [apps, setApps] = useState(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("toutes");
  const [sort, setSort] = useState("recent");
  const [busyId, setBusyId] = useState(0);

  useEffect(() => {
    api("/applications").then(setApps).catch((e) => setError(e.detail));
  }, []);

  async function changeStatus(appId, status) {
    setError("");
    setBusyId(appId);
    try {
      const updated = await api(`/applications/${appId}`, {
        method: "PATCH",
        body: { status },
      });
      setApps((list) => list.map((a) => (a.id === appId ? updated : a)));
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusyId(0);
    }
  }

  const filtered = useMemo(() => {
    const list = apps || [];
    if (tab === "encours") return list.filter((a) => !CLOSED.includes(a.status));
    if (tab === "entretien") return list.filter((a) => a.status === "entretien");
    if (tab === "cloturees") return list.filter((a) => CLOSED.includes(a.status));
    return list;
  }, [apps, tab]);

  const visible = useMemo(() => {
    const list = [...filtered];
    if (sort === "etape") {
      list.sort((a, b) => stepIndex(b.status) - stepIndex(a.status));
    } else if (sort === "entreprise") {
      list.sort((a, b) => (a.job.company || "").localeCompare(b.job.company || "", "fr"));
    } else {
      list.sort((a, b) => lastUpdate(b) - lastUpdate(a));
    }
    return list;
  }, [filtered, sort]);

  if (error && !apps) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!apps) {
    return <div className="page"><Loader /></div>;
  }

  const ongoing = apps.filter((a) => !CLOSED.includes(a.status));
  const interviews = apps.filter((a) => a.status === "entretien");
  const closed = apps.filter((a) => CLOSED.includes(a.status));
  const missingDocs = apps.filter(
    (a) => !CLOSED.includes(a.status) && a.documents.length === 0
  ).length;

  const tabCounts = {
    toutes: apps.length,
    encours: ongoing.length,
    entretien: interviews.length,
    cloturees: closed.length,
  };

  // Prochaine action : la candidature la plus utile à faire avancer.
  const nextAction = (() => {
    const interview = interviews[0];
    if (interview) {
      return {
        tone: "focus",
        icon: I.chat,
        title: "Préparez votre entretien",
        app: interview,
        text: `« ${interview.job.title} » chez ${interview.job.company} : questions probables, pitch et conseils générés depuis votre profil validé.`,
      };
    }
    const waiting = ongoing.find((a) => a.status === "en_attente");
    if (waiting) {
      return {
        tone: "wait",
        icon: I.clock,
        title: "Relancez votre candidature",
        app: waiting,
        text: `« ${waiting.job.title} » est en attente de réponse. Vérifiez vos messages, puis faites avancer l'étape : l'historique reste daté.`,
      };
    }
    const withoutDoc = ongoing.find((a) => a.documents.length === 0);
    if (withoutDoc) {
      return {
        tone: "open",
        icon: I.file,
        title: "Préparez vos documents",
        app: withoutDoc,
        text: `« ${withoutDoc.job.title} » n'a encore ni CV ciblé ni lettre. Les deux sont générés depuis votre profil validé.`,
      };
    }
    const last = ongoing[0];
    if (last) {
      return {
        tone: "open",
        icon: I.zap,
        title: "Faites avancer votre suivi",
        app: last,
        text: `« ${last.job.title} » est à l'étape « ${STATUS_LABELS[last.status]} ». Marquez l'étape suivante dès qu'elle est franchie.`,
      };
    }
    return null;
  })();

  const stats = [
    {
      tone: "green",
      icon: I.target,
      num: ongoing.length,
      label: `candidature${plural(ongoing.length, "", "s")} en cours`,
      note: "Hors candidatures acceptées et refusées",
    },
    {
      tone: "violet",
      icon: I.chat,
      num: interviews.length,
      label: `entretien${plural(interviews.length, "", "s")} à préparer`,
      note: "Pitch, questions probables et conseils",
    },
    {
      tone: "blue",
      icon: I.file,
      num: missingDocs,
      label: "sans document",
      note: "CV ciblé ou lettre à générer",
    },
  ];

  return (
    <div className="page apps-page">
      <div className="dash-columns">
        <div className="dash-col-main">
          {/* ---------- Bandeau ---------- */}
          <section className="home-hero apps-hero">
            <span className="apps-eyebrow">Mini-ATS personnel</span>
            <h1>Mes candidatures</h1>
            <p className="apps-hero-lead">
              Chaque candidature a son étape, ses documents et son historique daté.
            </p>
            <p className="apps-hero-note">
              {apps.length === 0
                ? "Vous ne suivez aucune candidature pour l'instant : ouvrez une offre qui vous intéresse et cliquez sur « Suivre ma candidature »."
                : `Vous suivez ${apps.length} candidature${plural(apps.length, "", "s")} : ${ongoing.length} encore en cours${interviews.length > 0 ? `, dont ${interviews.length} entretien${plural(interviews.length, "", "s")} à préparer` : ""}${closed.length > 0 ? `, et ${closed.length} clôturée${plural(closed.length, "", "s")}` : ""}. Les étapes que vous marquez restent datées et vérifiables.`}
            </p>
          </section>

          {/* ---------- Indicateurs réels ---------- */}
          <div className="opps-stats apps-stats">
            {stats.map((stat) => (
              <div className={`opps-stat opps-stat-${stat.tone}`} key={stat.label}>
                <span className="opps-stat-icon"><Icon d={stat.icon} size={18} /></span>
                <span className="opps-stat-num">{stat.num}</span>
                <span className="opps-stat-label">{stat.label}</span>
                <span className="opps-stat-note">{stat.note}</span>
              </div>
            ))}
          </div>

          {/* ---------- Liste ---------- */}
          <section className="dash-card apps-list">
            <div className="apps-toolbar">
              <div className="opps-tabs apps-tabs">
                {TABS.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`opps-tab${tab === item.id ? " is-active" : ""}`}
                    onClick={() => setTab(item.id)}
                  >
                    {item.label} ({tabCounts[item.id]})
                  </button>
                ))}
              </div>
              {apps.length > 1 && (
                <label className="apps-sort">
                  <span>Trier par</span>
                  <select value={sort} onChange={(e) => setSort(e.target.value)}>
                    {SORTS.map((item) => (
                      <option key={item.id} value={item.id}>{item.label}</option>
                    ))}
                  </select>
                </label>
              )}
            </div>

            <ErrorNote error={error} />

            {apps.length === 0 ? (
              <Empty title="Aucune candidature suivie">
                <p>
                  Repérez une offre intéressante puis cliquez sur « Suivre ma
                  candidature » : elle rejoint ce suivi, avec son étape et son
                  historique.
                </p>
                <Link className="btn btn-outline" to="/opportunites">
                  Parcourir les opportunités
                </Link>
              </Empty>
            ) : visible.length === 0 ? (
              <Empty title="Rien dans cette étape">
                <p>
                  Aucune candidature ne correspond à ce filtre pour le moment.
                </p>
              </Empty>
            ) : (
              <div className="apps-list-body">
                {visible.map((app) => (
                  <ApplicationCard
                    key={app.id}
                    app={app}
                    onStatus={changeStatus}
                    busy={busyId === app.id}
                  />
                ))}
              </div>
            )}
          </section>

          <AssistantChat compact suggestions={APPS_SUGGESTIONS} pageContext="Candidatures" />
        </div>

        {/* ---------- Colonne latérale ---------- */}
        <div className="dash-col-side">
          {nextAction && (
            <section className={`dash-card apps-next apps-next-${nextAction.tone}`}>
              <span className="apps-next-icon"><Icon d={nextAction.icon} size={18} /></span>
              <h2>{nextAction.title}</h2>
              <p>{nextAction.text}</p>
              <div className="apps-next-actions">
                <a className="btn btn-primary btn-small" href={`#app-${nextAction.app.id}`}>
                  Aller à la candidature
                </a>
                <Link
                  className="btn btn-outline btn-small"
                  to={`/opportunites/${nextAction.app.job_id}`}
                >
                  Voir l'offre
                </Link>
              </div>
            </section>
          )}

          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.clipboard} size={16} /> Répartition du suivi</h2>
            </div>
            {apps.length === 0 ? (
              <p className="apps-none">Aucune candidature à répartir.</p>
            ) : (
              <div className="apps-funnel">
                {PIPELINE.concat(["refusee", "retiree", "declinee"]).map((status) => {
                  const count = apps.filter((a) => a.status === status).length;
                  if (count === 0) return null;
                  const share = Math.round((count / apps.length) * 100);
                  return (
                    <div className="apps-funnel-row" key={status}>
                      <div className="apps-funnel-top">
                        <span className={`apps-status ${statusTone(status)}`}>
                          {STATUS_LABELS[status]}
                        </span>
                        <span className="apps-funnel-count">{count}</span>
                      </div>
                      <span className="apps-funnel-track">
                        <span
                          className={`apps-funnel-fill ${statusTone(status)}`}
                          style={{ width: `${Math.max(share, 6)}%` }}
                        />
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
            <p className="apps-note">
              Une étape n'apparaît ici que si elle est réellement occupée par une
              de vos candidatures.
            </p>
          </section>

          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.layers} size={16} /> Aller plus loin</h2>
            </div>
            <ul className="apps-links">
              <li>
                <Link to="/opportunites">
                  <Icon d={I.briefcase} size={15} /> Offres et missions
                </Link>
              </li>
              <li>
                <Link to="/documents">
                  <Icon d={I.file} size={15} /> Mes documents
                </Link>
              </li>
              <li>
                <Link to="/agent">
                  <Icon d={I.bot} size={15} /> Mon agent
                </Link>
              </li>
              <li>
                <Link to="/profil">
                  <Icon d={I.user} size={15} /> Mon profil
                </Link>
              </li>
            </ul>
          </section>

          <AgentSideCard
            page="Candidatures"
            hint="Ori peut préparer vos entretiens et faire le point sur chaque candidature envoyée."
          />
        </div>
      </div>
    </div>
  );
}
