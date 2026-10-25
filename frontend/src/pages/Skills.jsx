import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import {
  EVIDENCE_KIND_LABELS,
  PROFICIENCY_LABELS,
  SOURCE_LABELS,
  plural,
} from "../lib.js";
import { Icon, I, ArrowIcon, TrendIcon } from "../components/icons.jsx";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";
import AssistantChat from "../components/AssistantChat.jsx";
import AgentSideCard from "../components/AgentSideCard.jsx";

// Compétences (§32) : la matrice du jeune, niveau, source, preuves
// RÉELLES (expériences, projets, certifications, formations vérifiées)
// et demande du marché (§13).
//
// Rien n'est inventé (§47) : une preuve renvoie toujours à un élément du
// profil validé. Et l'absence de preuve n'est pas une absence de
// compétence (§48) : la ligne « à confirmer » invite à raconter
// l'expérience, pas à douter du jeune.

const SKILLS_SUGGESTIONS = [
  "Quelles compétences me manquent ?",
  "Quelles compétences sont les plus demandées ?",
  "Comment mes compétences se positionnent-elles ?",
  "Quelle formation suivre en priorité ?",
];

const LEVEL_TONE = {
  debutant: "low",
  intermediaire: "mid",
  avance: "high",
};

const STATUS_ICON = {
  verifiee: I.check,
  en_progression: I.clock,
  a_confirmer: I.alert,
};

// Statut local de repli si la progression vérifiable n'est pas chargée.
const FALLBACK_STATUS = {
  verifiee: "Appuyée par des preuves",
  en_progression: "En progression",
  a_confirmer: "À confirmer",
};

function DemandChip({ entry }) {
  if (!entry) {
    return <span className="sk-demand none">Non demandée</span>;
  }
  return (
    <span className={`sk-demand trend-${entry.trend}`}>
      <TrendIcon trend={entry.trend} size={11} />
      {" "}{entry.demand_count} offre{plural(entry.demand_count, "", "s")}
    </span>
  );
}

// ------------------------------------------------------------- ligne compétence

function SkillRow({ skill, market, progress, open, onToggle }) {
  const status = progress?.status || "a_confirmer";
  const statusLabel = progress?.status_label || FALLBACK_STATUS[status];
  const evidences = progress?.evidences || [];
  const nextStep = progress?.next_step || "";
  const demand = market || (progress?.demand
    ? { name: skill.skill, demand_count: progress.demand, trend: "stable", pct_change: 0 }
    : null);

  return (
    <div className={`sk-row ${open ? "open" : ""}`}>
      <button
        type="button"
        className="sk-row-head"
        onClick={onToggle}
        aria-expanded={open}
        title="Voir les preuves de cette compétence"
      >
        <span className="sk-row-main">
          <span className="sk-row-name">{skill.skill}</span>
          <span className="sk-row-meta">
            <span className={`sk-level sk-level-${LEVEL_TONE[skill.proficiency] || "low"}`}>
              {PROFICIENCY_LABELS[skill.proficiency] || skill.proficiency}
            </span>
            {" "}· {SOURCE_LABELS[skill.source] || skill.source}
          </span>
        </span>
        <DemandChip entry={demand} />
        <span className={`sk-status sk-status-${status}`}>
          <Icon d={STATUS_ICON[status] || I.alert} size={12} />
          {statusLabel}
        </span>
        <span className={`car-row-chev ${open ? "up" : ""}`}>
          <ArrowIcon direction={open ? "up" : "down"} size={12} />
        </span>
      </button>

      {open && (
        <div className="sk-row-body">
          {evidences.length > 0 ? (
            <ul className="sk-evidences">
              {evidences.map((e, i) => (
                <li key={i}>
                  <strong>{EVIDENCE_KIND_LABELS[e.kind] || e.kind}</strong>
                  <span> {e.label}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="sk-no-evidence">
              Aucune preuve rattachée pour l'instant. Une expérience, y
              compris informelle, un projet ou une certification, racontés
              dans votre profil, appuiera cette compétence auprès des
              recruteurs.
            </p>
          )}
          {nextStep && (
            <p className="sk-next">
              <Icon d={I.lightbulb} size={13} /> {nextStep}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------- page

export default function Skills() {
  const [profile, setProfile] = useState(undefined);
  const [market, setMarket] = useState(null);
  const [progress, setProgress] = useState(null);
  const [openRows, setOpenRows] = useState(() => new Set());

  useEffect(() => {
    api("/profile").then(setProfile).catch(() => setProfile(null));
    api("/skills/market").then(setMarket).catch(() => {});
    // La progression vérifiable (preuves par compétence) vit avec le plan
    // d'apprentissage : mêmes données, zéro invention.
    api("/learning")
      .then((body) => setProgress(body.progress || []))
      .catch(() => setProgress([]));
  }, []);

  const demandMap = useMemo(() => {
    const map = {};
    (market || []).forEach((m) => { map[m.name] = m; });
    return map;
  }, [market]);

  const progressMap = useMemo(() => {
    const map = {};
    (progress || []).forEach((p) => { map[p.skill] = p; });
    return map;
  }, [progress]);

  if (profile === undefined) {
    return <div className="page"><Loader /></div>;
  }
  if (profile === null) {
    return (
      <div className="page sk-page">
        <h1>Compétences</h1>
        <Empty title="Aucun profil pour le moment">
          <p>Construisez votre profil pour voir votre matrice de compétences.</p>
          <Link className="btn btn-primary" to="/onboarding">Construire mon profil</Link>
        </Empty>
      </div>
    );
  }

  const skills = profile.skills || [];
  if (skills.length === 0) {
    return (
      <div className="page sk-page">
        <h1>Compétences</h1>
        <Empty title="Aucune compétence enregistrée">
          <p>Ajoutez vos compétences depuis la page Profil.</p>
          <Link className="btn btn-outline" to="/profil">Modifier mon profil</Link>
        </Empty>
      </div>
    );
  }

  // Matrice groupée par catégorie, la plus demandée en tête de groupe.
  const byCategory = {};
  skills.forEach((s) => {
    const cat = s.category || "Autres";
    (byCategory[cat] = byCategory[cat] || []).push(s);
  });
  const categories = Object.keys(byCategory).sort((a, b) => a.localeCompare(b, "fr"));
  const demandOf = (s) => progressMap[s.skill]?.demand ?? demandMap[s.skill]?.demand_count ?? 0;
  categories.forEach((cat) => {
    byCategory[cat].sort((a, b) => (demandOf(b) - demandOf(a)) || a.skill.localeCompare(b.skill, "fr"));
  });

  const verified = skills.filter((s) => (progressMap[s.skill]?.status) === "verifiee").length;
  const inMarket = skills.filter((s) => demandOf(s) > 0).length;
  const toConfirm = skills.filter((s) => (progressMap[s.skill]?.status || "a_confirmer") === "a_confirmer").length;

  const stats = [
    {
      tone: "green", icon: I.layers, num: skills.length,
      label: `compétence${plural(skills.length, "", "s")} au profil`,
      note: `niveau et source, modifiables depuis le profil`,
    },
    {
      tone: "violet", icon: I.shield, num: verified,
      label: `appuyée${plural(verified, "", "s")} par des preuves`,
      note: "expériences, projets, certifications, formations vérifiées",
    },
    {
      tone: "blue", icon: I.trending, num: inMarket,
      label: `demandée${plural(inMarket, "", "s")} par le marché`,
      note: "sur les offres actives",
    },
    {
      tone: "orange", icon: I.alert, num: toConfirm,
      label: `à confirmer`,
      note: "sans preuve rattachée pour l'instant, pas sans valeur (§48)",
    },
  ];

  // Marché : les plus demandées, avec la marque « déjà au profil ».
  const topMarket = (market || []).slice().sort((a, b) => b.demand_count - a.demand_count).slice(0, 10);
  const maxDemand = topMarket[0]?.demand_count || 1;
  const profileSkillNames = new Set(skills.map((s) => s.skill));

  function toggleRow(name) {
    setOpenRows((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  return (
    <div className="page sk-page">
      <div className="dash-columns">
        <div className="dash-col-main">
          {/* ---------- Bandeau ---------- */}
          <section className="home-hero sk-hero">
            <span className="sk-eyebrow">Preuves et marché</span>
            <h1>Compétences</h1>
            <p className="sk-hero-lead">
              Votre matrice : niveau, source, preuves issues de votre profil,
              et demande réelle observée sur le marché.
            </p>
            <p className="sk-hero-note">
              Rien n'est inventé : chaque preuve renvoie à une expérience, un
              projet, une certification ou une formation vérifiée. Et
              l'absence de preuve n'est pas une absence de compétence : la
              ligne « à confirmer » invite à raconter ce que vous avez fait.
            </p>
          </section>

          {/* ---------- Indicateurs réels ---------- */}
          <div className="opps-stats sk-stats">
            {stats.map((s) => (
              <div className={`opps-stat opps-stat-${s.tone}`} key={s.label}>
                <span className="opps-stat-icon"><Icon d={s.icon} size={18} /></span>
                <span className="opps-stat-num">{s.num}</span>
                <span className="opps-stat-label">{s.label}</span>
                <span className="opps-stat-note">{s.note}</span>
              </div>
            ))}
          </div>

          {/* ---------- Matrice par catégorie ---------- */}
          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.layers} size={16} /> Ma matrice de compétences</h2>
              <span className="sk-head-note">
                cliquez sur une compétence pour voir ses preuves
              </span>
            </div>
            {categories.map((cat) => (
              <div className="sk-cat" key={cat}>
                <div className="sk-cat-head">
                  <h3>{cat}</h3>
                  <span className="sk-cat-count">
                    {byCategory[cat].length} compétence{plural(byCategory[cat].length, "", "s")}
                    {" "}· {byCategory[cat].filter((s) => progressMap[s.skill]?.status === "verifiee").length} appuyée{plural(byCategory[cat].filter((s) => progressMap[s.skill]?.status === "verifiee").length, "", "s")}
                  </span>
                </div>
                <div className="sk-rows">
                  {byCategory[cat].map((s) => (
                    <SkillRow
                      key={s.skill}
                      skill={s}
                      market={demandMap[s.skill]}
                      progress={progressMap[s.skill]}
                      open={openRows.has(s.skill)}
                      onToggle={() => toggleRow(s.skill)}
                    />
                  ))}
                </div>
              </div>
            ))}
            <p className="sk-edit-note">
              Vos compétences se modifient depuis la page{" "}
              <Link to="/profil">Profil</Link>, jamais ici : cette matrice
              reflète votre profil validé.
            </p>
          </section>

          {/* ---------- Marché ---------- */}
          {topMarket.length > 0 && (
            <section className="dash-card sk-market">
              <div className="dash-card-head">
                <h2><Icon d={I.trending} size={16} /> Ce que le marché demande</h2>
                <span className="sk-head-note">
                  ✓ déjà au profil · ○ absente du profil
                </span>
              </div>
              <ul className="car-bars" aria-label="Compétences les plus demandées">
                {topMarket.map((m) => {
                  const have = profileSkillNames.has(m.name);
                  return (
                    <li key={m.name}>
                      <span className="car-bar-label">{m.name}</span>
                      <span className="car-bar-track">
                        <span
                          className="car-bar-fill"
                          style={{ width: `${Math.max(6, Math.round(100 * m.demand_count / maxDemand))}%` }}
                        />
                      </span>
                      <span className="car-bar-count">
                        {m.demand_count} offre{plural(m.demand_count, "", "s")}
                      </span>
                      <span className={`sk-mark ${have ? "sk-mark-have" : "sk-mark-miss"}`}>
                        {have ? "✓" : "○"}
                      </span>
                    </li>
                  );
                })}
              </ul>
              <p className="sk-market-note">
                Les compétences ○ absentes de votre profil se travaillent
                depuis la page{" "}
                <Link to="/learning">Apprentissage</Link> : une formation
                terminée avec sa pièce devient une preuve.
              </p>
            </section>
          )}

          <AssistantChat compact suggestions={SKILLS_SUGGESTIONS} pageContext="Competences" />
        </div>

        {/* ---------- Colonne latérale ---------- */}
        <div className="dash-col-side">
          <AgentSideCard
            page="Competences"
            hint="Ori peut prioriser les compétences qui manquent le plus dans les offres de votre domaine."
          />
          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.shield} size={16} /> D'où viennent les preuves</h2>
            </div>
            <ul className="sk-kinds">
              <li>
                <Icon d={I.briefcase} size={14} />
                <div>
                  <strong>Expérience</strong>
                  <p>Emploi, stage, activité informelle, mission freelance.</p>
                </div>
              </li>
              <li>
                <Icon d={I.folder} size={14} />
                <div>
                  <strong>Projet</strong>
                  <p>Réalisation personnelle ou projet guidé.</p>
                </div>
              </li>
              <li>
                <Icon d={I.award} size={14} />
                <div>
                  <strong>Certification</strong>
                  <p>Certificat, badge ou attestation, avec sa référence.</p>
                </div>
              </li>
              <li>
                <Icon d={I.cap} size={14} />
                <div>
                  <strong>Formation</strong>
                  <p>Suivie et vérifiée sur présentation de la pièce (§47).</p>
                </div>
              </li>
            </ul>
          </section>

          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.clipboard} size={16} /> Faire reconnaître une compétence</h2>
            </div>
            <ol className="learn-howto-steps">
              <li>
                <span className="learn-howto-num">1</span>
                <div>
                  <strong>Raconter l'expérience</strong>
                  <p>
                    Formelle ou informelle, elle compte :{" "}
                    <Link to="/profil">ajoutez-la à votre profil</Link>.
                  </p>
                </div>
              </li>
              <li>
                <span className="learn-howto-num">2</span>
                <div>
                  <strong>La faire vivre</strong>
                  <p>
                    Un projet ou une{" "}
                    <Link to="/learning">formation vérifiable</Link> ajoute
                    une preuve solide.
                  </p>
                </div>
              </li>
              <li>
                <span className="learn-howto-num">3</span>
                <div>
                  <strong>Elle pèse dans le matching</strong>
                  <p>
                    Les preuves apparaissent ici et dans{" "}
                    <Link to="/carriere">vos pistes métiers</Link>.
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
                <Link to="/profil">
                  <Icon d={I.user} size={15} /> Modifier mon profil
                </Link>
              </li>
              <li>
                <Link to="/learning">
                  <Icon d={I.book} size={15} /> Formations vérifiables
                </Link>
              </li>
              <li>
                <Link to="/opportunites">
                  <Icon d={I.briefcase} size={15} /> Les offres qui demandent ces compétences
                </Link>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
