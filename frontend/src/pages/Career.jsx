import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import MatchBadge from "../components/MatchBadge.jsx";
import SkillTag from "../components/SkillTag.jsx";
import { ACCESSIBILITY_LABELS, plural } from "../lib.js";
import { Icon, I, ArrowIcon, TrendIcon } from "../components/icons.jsx";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";
import AssistantChat from "../components/AssistantChat.jsx";
import AgentSideCard from "../components/AgentSideCard.jsx";

// Carrière (§9, §9bis, §33) : pistes métiers + lecture du marché (§13).
//
// Rien n'est prescrit : chaque métier affiche son score EXPLICABLE (§12) :
// ✓ couvertes, △ partielles, ○ manquantes, ses atouts, sa lecture en
// français et l'horizon d'accès réel (tout de suite, après une montée en
// compétences, ou plus long terme). L'orientation est une aide à la
// décision ; le marché n'est là que pour contextualiser, jamais inventer.

const CAREER_SUGGESTIONS = [
  "Quel métier me correspond le mieux ?",
  "Comment atteindre ce métier ?",
  "Quelles compétences monter en priorité ?",
  "Et si je créais mon activité ?",
];

// Nombre de pistes détaillées en grand ; les autres restent pliables.
const TOP_COUNT = 3;

const ACCESS_ICON = {
  immediate: I.zap,
  with_upskilling: I.award,
  long_term: I.clock,
};

function AccessibilityChip({ value }) {
  return (
    <span className={`car-access car-access-${value}`}>
      <Icon d={ACCESS_ICON[value] || I.clock} size={13} />
      {ACCESSIBILITY_LABELS[value] || value}
    </span>
  );
}

// ------------------------------------------------------------------ carte métier

function CareerCard({ career, rank }) {
  const m = career.match;
  return (
    <article className="car-card">
      <header className="car-head">
        <div className="car-head-main">
          {rank > 0 && <span className="car-rank">Piste {rank}</span>}
          <h3>{career.title}</h3>
          <p className="car-meta">{career.family}</p>
        </div>
        <div className="car-head-side">
          <MatchBadge score={m.score} />
          <AccessibilityChip value={m.accessibility} />
        </div>
      </header>

      <p className="car-desc">{career.description}</p>

      <div className="car-explain">
        <span className="car-explain-icon"><Icon d={I.lightbulb} size={15} /></span>
        <p>{m.explanation}</p>
      </div>

      {m.strengths.length > 0 && (
        <div className="car-strengths">
          <h4 className="car-sub">Vos atouts sur ce métier</h4>
          <ul>
            {m.strengths.map((s) => (
              <li key={s}><Icon d={I.check} size={13} /> {s}</li>
            ))}
          </ul>
        </div>
      )}

      <h4 className="car-sub">Compétences attendues, face à votre profil</h4>
      <div className="car-skills">
        {m.covered.map((s) => <SkillTag key={s} name={s} state="covered" />)}
        {m.partial.map((s) => <SkillTag key={s} name={s} state="partial" />)}
        {m.missing.map((s) => <SkillTag key={s} name={s} state="missing" />)}
      </div>

      <h4 className="car-sub">Pour y arriver</h4>
      <ul className="explain-list">
        {m.recommended_actions.map((a, i) => <li key={i}>{a}</li>)}
      </ul>

      {career.related_jobs && career.related_jobs.length > 0 && (
        <div className="car-jobs">
          <h4 className="car-sub">
            Offres actives liées
            <span className="car-head-note">
              {" "}{career.related_jobs.length} offre{plural(career.related_jobs.length, "", "s")} sur le marché
            </span>
          </h4>
          <ul>
            {career.related_jobs.map((j) => (
              <li key={j.id}>
                <Link to={`/opportunites/${j.id}`}>
                  <span className="car-job-main">
                    <strong>{j.title}</strong>
                    <span>{j.company} · {j.location} · {j.contract_type}</span>
                  </span>
                  <ArrowIcon direction="right" size={13} />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="car-cta">
        <Link className="btn btn-outline btn-small" to="/learning">
          Monter ces compétences <ArrowIcon direction="right" size={12} />
        </Link>
        <Link className="btn btn-outline btn-small" to="/opportunites">
          Voir les offres <ArrowIcon direction="right" size={12} />
        </Link>
      </div>
    </article>
  );
}

// Ligne pliable pour les pistes moins proches : le détail reste accessible,
// la page reste lisible.
function CareerRow({ career, open, onToggle }) {
  const m = career.match;
  return (
    <div className={`car-row ${open ? "open" : ""}`}>
      <button type="button" className="car-row-head" onClick={onToggle} aria-expanded={open}>
        <span className="car-row-title">{career.title}</span>
        <span className="car-row-family">{career.family}</span>
        <span className="car-row-access">
          {ACCESSIBILITY_LABELS[m.accessibility]}
        </span>
        <MatchBadge score={m.score} />
        <span className={`car-row-chev ${open ? "up" : ""}`}>
          <ArrowIcon direction={open ? "up" : "down"} size={12} />
        </span>
      </button>
      {open && (
        <div className="car-row-body">
          <CareerCard career={career} />
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------- marché

function BarList({ items, label, max, kind }) {
  return (
    <ul className="car-bars" aria-label={label}>
      {items.map((s) => {
        const value = kind === "skills" ? s.count : s.offers;
        return (
          <li key={s.name}>
            <span className="car-bar-label">{s.name}</span>
            <span className="car-bar-track">
              <span className="car-bar-fill" style={{ width: `${Math.max(6, Math.round(100 * value / max))}%` }} />
            </span>
            <span className="car-bar-count">
              {value} offre{plural(value, "", "s")}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function MarketCard({ market }) {
  if (!market) return null;
  const maxSkill = market.top_skills[0]?.count || 1;
  const maxSector = market.sectors[0]?.offers || 1;
  return (
    <section className="dash-card">
      <div className="dash-card-head">
        <h2><Icon d={I.chart} size={16} /> Marché observé</h2>
        <span className="car-head-note">calculé sur les offres actives, aucune donnée inventée</span>
      </div>
      <div className="car-market-grid">
        <div>
          <h3 className="car-sub">Compétences les plus demandées</h3>
          <BarList items={market.top_skills.slice(0, 8)} label="Compétences les plus demandées" max={maxSkill} kind="skills" />
        </div>
        <div>
          <h3 className="car-sub">Secteurs qui recrutent</h3>
          <BarList items={market.sectors.slice(0, 6)} label="Secteurs qui recrutent" max={maxSector} kind="sectors" />
          <h3 className="car-sub">Mouvements</h3>
          <div className="car-moves">
            <p className="car-moves-kind">
              <TrendIcon trend="up" /> En hausse
            </p>
            <div className="chip-row">
              {market.trending_up.length > 0
                ? market.trending_up.map((s) => <span key={s} className="chip">{s}</span>)
                : <span className="muted small">Aucune hausse marquée</span>}
            </div>
            <p className="car-moves-kind">
              <TrendIcon trend="down" /> En baisse
            </p>
            <div className="chip-row">
              {market.trending_down.length > 0
                ? market.trending_down.map((s) => <span key={s} className="chip">{s}</span>)
                : <span className="muted small">Aucune baisse marquée</span>}
            </div>
            <p className="car-moves-kind">Émergentes</p>
            <div className="chip-row">
              {market.emerging.length > 0
                ? market.emerging.map((s) => <span key={s} className="chip chip-warn">{s}</span>)
                : <span className="muted small">Aucune compétence émergente repérée</span>}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// --------------------------------------------------------------------- page

export default function Career() {
  const [careers, setCareers] = useState(null);
  const [market, setMarket] = useState(null);
  const [error, setError] = useState("");
  const [openRows, setOpenRows] = useState(() => new Set());

  useEffect(() => {
    Promise.all([
      api("/careers").catch((e) => setError(e.detail)),
      api("/market/trends").catch(() => null),
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

  const hasProfile = careers.length > 0 && careers[0].match.score > 0;
  const top = hasProfile ? careers.slice(0, TOP_COUNT) : [];
  const rest = hasProfile ? careers.slice(TOP_COUNT) : [];
  const within = careers.filter((c) => c.match.score >= 45).length;
  const immediate = careers.filter((c) => c.match.accessibility === "immediate").length;
  // Offres UNIQUES liées (une même offre peut servir plusieurs métiers).
  const linkedIds = new Set();
  careers.forEach((c) => (c.related_jobs || []).forEach((j) => linkedIds.add(j.id)));
  const linked = linkedIds.size;
  const best = hasProfile ? careers[0] : null;

  const stats = [
    {
      tone: "green", icon: I.target, num: within,
      label: `métier${plural(within, "", "s")} à portée`,
      note: "adéquation moyenne ou forte",
    },
    {
      tone: "violet", icon: I.award, num: best ? best.match.score : 0,
      label: "meilleure piste",
      note: best ? best.title : "Construisez votre profil",
    },
    {
      tone: "blue", icon: I.zap, num: immediate,
      label: `accessible${plural(immediate, "", "s")} tout de suite`,
      note: "avec votre profil actuel",
    },
    {
      tone: "orange", icon: I.briefcase, num: linked,
      label: `offre${plural(linked, "", "s")} liée${plural(linked, "", "s")}`,
      note: "actives et reliées à vos pistes",
    },
  ];

  function toggleRow(id) {
    setOpenRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="page car-page">
      <div className="dash-columns">
        <div className="dash-col-main">
          {/* ---------- Bandeau ---------- */}
          <section className="home-hero car-hero">
            <span className="car-eyebrow">Orientation</span>
            <h1>Carrière</h1>
            <p className="car-hero-lead">
              Des métiers compatibles avec votre profil réel, accessibles
              maintenant, ou après une montée en compétences ciblée.
            </p>
            <p className="car-hero-note">
              Chaque score s'explique compétence par compétence : ✓ couverte,
              △ partielle, ○ manquante. L'orientation est une aide à la
              décision, pas une prescription.
            </p>
          </section>

          {/* ---------- Indicateurs réels ---------- */}
          <div className="opps-stats car-stats">
            {stats.map((s) => (
              <div className={`opps-stat opps-stat-${s.tone}`} key={s.label}>
                <span className="opps-stat-icon"><Icon d={s.icon} size={18} /></span>
                <span className="opps-stat-num">{s.num}</span>
                <span className="opps-stat-label">{s.label}</span>
                <span className="opps-stat-note">{s.note}</span>
              </div>
            ))}
          </div>

          <ErrorNote error={error} />

          {/* ---------- Pistes ---------- */}
          {!hasProfile && (
            <Empty title="Construisez d'abord votre profil">
              <p>
                Les pistes métiers se calculent à partir de vos compétences
                réelles : sans profil, aucun score honnête n'est possible,
                et rien n'est inventé.
              </p>
              <Link className="btn btn-outline" to="/profil">Compléter mon profil</Link>
            </Empty>
          )}

          {top.length > 0 && (
            <section className="dash-card">
              <div className="dash-card-head">
                <h2><Icon d={I.compass} size={16} /> Vos meilleures pistes</h2>
                <span className="car-head-note">classées par adéquation avec votre profil</span>
              </div>
              <div className="car-list">
                {top.map((c, i) => (
                  <CareerCard key={c.id} career={c} rank={i + 1} />
                ))}
              </div>
            </section>
          )}

          {rest.length > 0 && (
            <section className="dash-card">
              <div className="dash-card-head">
                <h2><Icon d={I.layers} size={16} /> Autres métiers explorés</h2>
                <span className="car-head-note">
                  {rest.length} piste{plural(rest.length, "", "s")} plus éloignée{plural(rest.length, "", "s")}. Cliquez pour le détail
                </span>
              </div>
              <div className="car-rows">
                {rest.map((c) => (
                  <CareerRow
                    key={c.id}
                    career={c}
                    open={openRows.has(c.id)}
                    onToggle={() => toggleRow(c.id)}
                  />
                ))}
              </div>
            </section>
          )}

          {/* ---------- Marché ---------- */}
          <MarketCard market={market} />

          <AssistantChat compact suggestions={CAREER_SUGGESTIONS} pageContext="Carriere" />
        </div>

        {/* ---------- Colonne latérale ---------- */}
        <div className="dash-col-side">
          <AgentSideCard
            page="Carriere"
            hint="Ori peut expliquer les passerelles réalistes depuis votre profil et les compétences à combler."
          />
          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.clipboard} size={16} /> Comment lire un score</h2>
            </div>
            <ul className="car-legend">
              <li>
                <SkillTag name="Compétence" state="covered" />
                <span>couverte : vous la maîtrisez au-delà du niveau débutant</span>
              </li>
              <li>
                <SkillTag name="Compétence" state="partial" />
                <span>partielle : niveau débutant, elle compte à moitié</span>
              </li>
              <li>
                <SkillTag name="Compétence" state="missing" />
                <span>manquante : absente de votre profil validé</span>
              </li>
            </ul>
            <p className="car-side-note">
              Les compétences essentielles pèsent plus lourd que les
              appréciées, et votre niveau renforce le poids. Un score n'est
              pas un verdict : c'est un point de départ pour agir.
            </p>
          </section>

          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.compass} size={16} /> Votre prochaine étape</h2>
            </div>
            <ol className="learn-howto-steps">
              <li>
                <span className="learn-howto-num">1</span>
                <div>
                  <strong>Choisir une piste</strong>
                  <p>Comparez les trois premières : score, atouts, horizon d'accès.</p>
                </div>
              </li>
              <li>
                <span className="learn-howto-num">2</span>
                <div>
                  <strong>Combler les écarts</strong>
                  <p>
                    <Link to="/learning">La page Apprentissage</Link> liste les
                    formations qui couvrent exactement vos ○ manquantes.
                  </p>
                </div>
              </li>
              <li>
                <span className="learn-howto-num">3</span>
                <div>
                  <strong>Postuler avec un CV ciblé</strong>
                  <p>
                    <Link to="/opportunites">Les offres liées</Link> acceptent un
                    CV généré uniquement à partir de votre profil validé.
                  </p>
                </div>
              </li>
              <li>
                <span className="learn-howto-num">4</span>
                <div>
                  <strong>Suivre vos candidatures</strong>
                  <p>
                    <Link to="/candidatures">Votre suivi</Link> trace chaque étape
                    franchie, sans rien inventer.
                  </p>
                </div>
              </li>
            </ol>
          </section>

          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.link} size={16} /> Aller plus loin</h2>
            </div>
            <ul className="learn-links">
              <li>
                <Link to="/competences">
                  <Icon d={I.activity} size={15} /> Mes compétences et preuves
                </Link>
              </li>
              <li>
                <Link to="/learning">
                  <Icon d={I.book} size={15} /> Formations vérifiables
                </Link>
              </li>
              <li>
                <Link to="/entrepreneuriat">
                  <Icon d={I.rocket} size={15} /> Et si vous créiez votre activité ?
                </Link>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
