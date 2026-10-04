import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { Icon, I, ArrowIcon, TrendIcon } from "../components/icons.jsx";
import { Loader, ErrorNote } from "../components/ui.jsx";
import { relTime } from "../lib.js";

// Dashboard Talent : un poste de pilotage où l'IA travaille POUR le
// jeune. Hiérarchie : 1) briefing personnalisé de l'IA, 2) action
// prioritaire, 3) signaux clés, 4) meilleure piste et marché, 5) flux.
// Chaque bloc est cliquable : le dashboard mène à l'action (§73).

function CompletenessRing({ score }) {
  const radius = 30;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 80 ? "#0e5c3a" : score >= 50 ? "#e67e22" : "#a83232";
  return (
    <svg width="76" height="76" viewBox="0 0 76 76" style={{ transform: "rotate(-90deg)" }}>
      <circle cx="38" cy="38" r={radius} fill="none" stroke="#e6ebe7" strokeWidth="7" />
      <circle
        cx="38" cy="38" r={radius} fill="none"
        stroke={color} strokeWidth="7" strokeLinecap="round"
        strokeDasharray={circumference} strokeDashoffset={offset}
      />
      <text
        x="38" y="43" textAnchor="middle"
        style={{ transform: "rotate(90deg)", transformOrigin: "38px 38px" }}
        fill={color} fontSize="17" fontWeight="700" fontFamily="inherit"
      >
        {score}%
      </text>
    </svg>
  );
}

function StatCard({ icon, value, label, to }) {
  return (
    <Link className="stat-card" to={to}>
      <span className="stat-card-icon"><Icon d={icon} /></span>
      <span className="stat-card-value">{value}</span>
      <span className="stat-card-label">{label}</span>
    </Link>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [profile, setProfile] = useState(undefined);
  const [events, setEvents] = useState([]);
  const [unread, setUnread] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/dashboard").then(setData).catch((e) => setError(e.detail));
    api("/profile").then(setProfile).catch(() => setProfile(null));
    api("/inbox").then(setEvents).catch(() => setEvents([]));
    api("/messages/unread-count").then((d) => setUnread(d.count)).catch(() => {});
  }, []);

  if (error) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!data || profile === undefined) {
    return <div className="page"><Loader /></div>;
  }

  const firstName = (data.name || "").split(" ")[0];
  const today = new Date().toLocaleDateString("fr-FR", {
    weekday: "long", day: "numeric", month: "long",
  });
  const comp = data.profile_completeness;
  const nextTo = data.next_action.job_id
    ? `/opportunites/${data.next_action.job_id}`
    : "/learning";
  const nextLabel =
    data.next_action.type === "learn" ? "Voir les ressources"
      : data.next_action.type === "prepare_interview" ? "Préparer l'entretien"
        : "Passer à l'action";

  // ---- État 1 : pas encore de profil
  if (profile === null) {
    return (
      <div className="page">
        <header className="dash-header">
          <div>
            <h1>Bonjour {firstName}</h1>
            <p className="dash-date">{today}</p>
          </div>
        </header>
        <section className="ai-card">
          <span className="ai-mark"><Icon d={I.spark} size={20} /></span>
          <div>
            <p className="ai-label">Votre assistant OrientSkill</p>
            <p className="ai-briefing">{data.ai_briefing}</p>
          </div>
        </section>
        <div className="dash-hero-buttons">
          <Link className="btn btn-primary" to="/onboarding">Importer mon CV</Link>
          <Link className="btn btn-outline" to="/questionnaire">Créer mon profil</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      {/* ---------- En-tête ---------- */}
      <header className="dash-header">
        <div>
          <h1>Bonjour {firstName}</h1>
          <p className="dash-date">{today}</p>
        </div>
        <div className="dash-header-side">
          {comp && comp.score >= 80 && (
            <span className="dash-chip dash-chip-ok">
              <Icon d={I.check} size={13} /> Profil solide
            </span>
          )}
          {profile.availability && (
            <span className="dash-chip">Disponibilité : {profile.availability}</span>
          )}
        </div>
      </header>

      {/* ---------- Briefing IA ---------- */}
        <section className="ai-card">
          <span className="ai-mark"><Icon d={I.spark} size={20} /></span>
          <div className="ai-card-body">
            <p className="ai-label">{data.ai_label || "Votre assistant a analysé votre situation"}</p>
            <p className="ai-briefing">{data.ai_briefing}</p>
          <div className="ai-card-actions">
            <Link className="btn btn-primary btn-small" to={nextTo}>
              {nextLabel} <ArrowIcon direction="right" size={13} />
            </Link>
            <Link className="btn btn-ghost btn-small" to="/assistant">
              Parler à l'assistant
            </Link>
          </div>
        </div>
      </section>

      {/* ---------- Messages non lus ---------- */}
      {unread > 0 && (
        <Link className="unread-banner" to="/messages">
          <Icon d={I.mail} size={16} />
          <span>
            {unread} message{unread > 1 ? "s" : ""} non lu{unread > 1 ? "s" : ""} :
            un recruteur vous attend peut-être.
          </span>
          <Icon d={I.arrow} size={15} />
        </Link>
      )}

      {/* ---------- Signaux clés ---------- */}
      <div className="stat-grid">
        <StatCard icon={I.trending} value={data.new_opportunities} label="nouvelles opportunités" to="/opportunites" />
        <StatCard icon={I.target} value={data.strong_matches} label="correspondances fortes" to="/opportunites?min_score=75" />
        <StatCard icon={I.clipboard} value={data.ongoing_applications} label="candidatures en cours" to="/candidatures" />
        <StatCard icon={I.chat} value={data.interviews_to_prepare} label="entretien(s) à préparer" to="/candidatures" />
      </div>

      {/* ---------- Deux colonnes : piste + profil ---------- */}
      <div className="dash-columns">
        <div className="dash-col-main">
          {/* Meilleure piste */}
          {data.top_matches.length > 0 && (
            <section className="dash-card">
              <div className="dash-card-head">
                <h2>Votre meilleure piste du moment</h2>
                <Link className="small" to="/opportunites">Toutes les offres <ArrowIcon direction="right" /></Link>
              </div>
              {data.top_matches.map((m) => (
                <Link key={m.id} className="match-row" to={`/opportunites/${m.id}`}>
                  <div>
                    <strong>{m.title}</strong>
                    <p className="match-row-meta">
                      {m.company} · {m.location} · {m.contract_type}
                    </p>
                  </div>
                  <span className={`match-pill match-${m.score >= 75 ? "strong" : "medium"}`}>
                    {m.score}/100
                  </span>
                </Link>
              ))}
            </section>
          )}

          {/* Marché */}
          <section className="dash-card">
            <div className="dash-card-head">
              <h2>Marché cette semaine</h2>
              <Link className="small" to="/carriere">Analyse complète <ArrowIcon direction="right" /></Link>
            </div>
            <p className="small muted" style={{ marginTop: 0 }}>
              {data.market_week.offers_in_period} offre(s) publiée(s) entre le{" "}
              {data.market_week.period_label}.
            </p>
            {data.market_trends.length > 0 ? (
              <ul className="trend-list">
                {data.market_trends.slice(0, 4).map((t) => (
                  <li key={t.name}>
                    <span>{t.name} <span className="small muted">({t.count} offre(s))</span></span>
                    <span className={`trend trend-${t.trend}`}>
                      <TrendIcon trend={t.trend} /> {t.pct_change > 0 ? `+${t.pct_change}` : t.pct_change} %
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small">Aucune offre publiée ces 7 derniers jours.</p>
            )}
          </section>

          {/* Flux récent */}
          {events.length > 0 && (
            <section className="dash-card">
              <div className="dash-card-head">
                <h2>Activité récente</h2>
                <Link className="small" to="/inbox">Tout voir <ArrowIcon direction="right" /></Link>
              </div>
              {events.slice(0, 4).map((ev) => (
                <p key={ev.id} className="small dash-event">
                  <span className="muted">{relTime(ev.at)}</span> · {ev.message}
                  {ev.job_id && (
                    <Link className="small" to={`/opportunites/${ev.job_id}`} style={{ marginLeft: "0.4rem" }}>
                      Voir
                    </Link>
                  )}
                </p>
              ))}
            </section>
          )}
        </div>

        {/* Colonne latérale : complétude */}
        <div className="dash-col-side">
          {comp && (
            <section className="dash-card dash-completeness">
              <div className="dash-card-head">
                <h2>Force du profil</h2>
              </div>
              <div className="completeness-head">
                <CompletenessRing score={comp.score} />
                <p className="small muted" style={{ margin: 0 }}>
                  {comp.score >= 80
                    ? "Votre profil est solide : continuez à le tenir à jour."
                    : "Chaque case cochée renforce votre matching et vos documents."}
                </p>
              </div>
              <ul className="completeness-list">
                {comp.checked.map((c) => (
                  <li key={c.key} className={c.done ? "done" : ""}>
                    {c.done
                      ? <Icon d={I.check} size={14} />
                      : <span className="completeness-todo" />}
                    <span>{c.label}</span>
                  </li>
                ))}
              </ul>
              {comp.missing.length > 0 && (
                <Link className="btn btn-outline btn-small" to="/profil">
                  Compléter mon profil
                </Link>
              )}
            </section>
          )}

          {data.skills_to_improve.length > 0 && (
            <section className="dash-card">
              <div className="dash-card-head">
                <h2>Compétences qui montent</h2>
              </div>
              <p className="small muted" style={{ marginTop: 0 }}>
                Demandées par les employeurs, à renforcer chez vous.
              </p>
              <div className="chip-row">
                {data.skills_to_improve.slice(0, 4).map((s) => (
                  <Link key={s} className="chip chip-warn" to="/learning">{s}</Link>
                ))}
              </div>
              <Link className="btn btn-ghost btn-small" to="/learning">
                Mon plan de formation
              </Link>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
