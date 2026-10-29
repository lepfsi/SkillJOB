import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api/client.js";
import {
  ENTREPRENEUR_KIND_LABELS, LEVEL_LABELS, fmtDate, plural, scoreLevel,
} from "../lib.js";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";
import { Icon, I, ArrowIcon } from "../components/icons.jsx";
import CompanyLogo from "../components/CompanyLogo.jsx";
import SkillTag from "../components/SkillTag.jsx";
import AssistantChat from "../components/AssistantChat.jsx";
import AgentSideCard from "../components/AgentSideCard.jsx";

// Espace entrepreneuriat (§11bis) : Ori est AU POSTE, pas un décor.
//
// L'agent lit le profil validé et :
//   1. situe les compétences entrepreneuriales (référentiel issu de notre
//      taxonomie) et les écarts à combler ;
//   2. propose des pistes concrètes dans NOTRE domaine de compétence ;
//   3. répertorie financements, concours, incubateurs et formations réels ;
//   4. génère le business plan à partir des chiffres du porteur.
//
// Rien n'est promis : des informations, des critères et des étapes.

const KINDS = ["concours", "accompagnement", "financement", "formation"];

const KIND_ICONS = {
  concours: I.award,
  accompagnement: I.users,
  financement: I.landmark,
  formation: I.book,
};

const ENT_SUGGESTIONS = [
  "Comment entreprendre dans mon domaine ?",
  "Quels financements pour mon projet ?",
  "Trouve des concours pour jeunes entrepreneurs",
  "Quelles compétences me manquent pour entreprendre ?",
];

// --------------------------------------------------------------- briques

function SkillGroup({ group }) {
  return (
    <div className="ent-group">
      <div className="ent-group-head">
        <span className="ent-group-label">{group.label}</span>
        <span className="ent-group-count">
          {group.covered + group.partial} / {group.total}
        </span>
      </div>
      {group.hint && <p className="ent-group-hint">{group.hint}</p>}
      <div className="ent-group-tags">
        {group.items.map((item) => (
          <SkillTag key={item.name} name={item.name} state={item.state} />
        ))}
      </div>
    </div>
  );
}

function ResourceCard({ resource }) {
  return (
    <article className="ent-res">
      <div className="ent-res-head">
        <span className="ent-res-icon">
          <Icon d={KIND_ICONS[resource.kind] || I.layers} size={16} />
        </span>
        <h3>{resource.title}</h3>
        <span className="ent-res-kind">{resource.kind_label}</span>
      </div>
      <p className="ent-res-desc">{resource.description}</p>
      <p className="ent-res-meta">
        {resource.organizer}
        {resource.sectors && resource.sectors.length > 0 && ` · ${resource.sectors.join(" · ")}`}
      </p>
      {resource.url && (
        <a className="link-more" href={resource.url} target="_blank" rel="noreferrer">
          Page officielle <ArrowIcon direction="right" size={12} />
        </a>
      )}
    </article>
  );
}

function BusinessPlanForm({ onCreated }) {
  const [form, setForm] = useState({ activity: "", target: "", capital: "", location: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState(null);

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const doc = await api("/entrepreneurship/business-plan", { method: "POST", body: form });
      setCreated(doc);
      onCreated(doc);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="ent-form" onSubmit={submit}>
      <ErrorNote error={error} />
      {created && (
        <div className="alert alert-success">
          Business plan généré.{" "}
          <Link to={`/documents?open=${created.id}`}>Ouvrir dans mes documents</Link>
        </div>
      )}
      <label className="field">
        <span>Votre activité ou projet *</span>
        <input
          value={form.activity}
          onChange={(e) => set("activity", e.target.value)}
          required
          placeholder="Ex. Installation et maintenance informatique pour PME"
        />
      </label>
      <div className="grid-2">
        <label className="field">
          <span>Clientèle visée</span>
          <input
            value={form.target}
            onChange={(e) => set("target", e.target.value)}
            placeholder="Ex. Commerces du quartier Akwa"
          />
        </label>
        <label className="field">
          <span>Capital de départ disponible</span>
          <input
            value={form.capital}
            onChange={(e) => set("capital", e.target.value)}
            placeholder="Ex. 350 000 FCFA"
          />
        </label>
      </div>
      <label className="field">
        <span>Localisation de l'activité</span>
        <input
          value={form.location}
          onChange={(e) => set("location", e.target.value)}
          placeholder="Ex. Douala (votre localisation de profil par défaut)"
        />
      </label>
      <div className="actions-row">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Je structure votre business plan…" : "Générer mon business plan"}
        </button>
      </div>
    </form>
  );
}

// ------------------------------------------------------------------ page

export default function Entrepreneurship() {
  const location = useLocation();
  const [data, setData] = useState(null);
  const [guidance, setGuidance] = useState(null);
  const [entre, setEntre] = useState(null);
  const [learning, setLearning] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [missions, setMissions] = useState([]);
  const [tab, setTab] = useState("all");
  const [error, setError] = useState("");

  useEffect(() => {
    api("/entrepreneurship").then(setData).catch((e) => setError(e.detail));
    api("/entrepreneurship/guidance").then(setGuidance).catch(() => setGuidance(null));
    api("/entrepreneurship/profile").then(setEntre).catch(() => setEntre(null));
    api("/learning").then(setLearning).catch(() => setLearning(null));
    api("/documents").then(setDocuments).catch(() => setDocuments([]));
    api("/jobs?contract_type=Freelance").then(setMissions).catch(() => setMissions([]));
  }, []);

  useEffect(() => {
    if (location.hash !== "#business-plan") return;
    const timer = setTimeout(
      () => document.getElementById("business-plan")?.scrollIntoView({ behavior: "smooth", block: "start" }),
      80,
    );
    return () => clearTimeout(timer);
  }, [location.hash]);

  if (error && !data) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!data) {
    return <div className="page"><Loader /></div>;
  }

  const resources = data.resources || [];
  const filtered = tab === "all" ? resources : resources.filter((r) => r.kind === tab);
  const plans = documents.filter((d) => d.kind === "business_plan");
  const groups = entre?.groups || [];
  const acquired = groups
    .flatMap((g) => g.items)
    .filter((i) => i.state !== "missing")
    .map((i) => i.name);
  const missingPriority = groups
    .flatMap((g) => g.items)
    .filter((i) => i.state === "missing")
    .slice(0, 5)
    .map((i) => i.name);
  const opportunities = guidance?.opportunities || [];
  const steps = guidance?.steps || [];
  const nextSkills = (learning?.learn_now || []).concat(learning?.learn_next || []).slice(0, 3);
  const domain = guidance?.category_label || null;

  const briefing = entre?.has_profile
    ? `D'après votre profil « ${entre.profile_title || "à préciser"} », votre domaine d'atout est le ${domain || "à préciser"}. `
      + `J'ai situé ${acquired.length} compétence${plural(acquired.length, "", "s")} entrepreneuriale${plural(acquired.length, "", "s")} déjà présente${plural(acquired.length, "", "s")} dans votre profil `
      + `et repéré ${resources.length} programme${plural(resources.length, "", "s")} et ${data.financing_institutions.length} pistes de financement réelles.`
    : "Votre profil n'est pas encore complet : je pourrai le situer précisément dès qu'il sera validé. "
      + "En attendant, les financements, concours et incubateurs sont déjà consultables.";

  const stats = [
    {
      icon: I.award,
      value: entre ? `${entre.covered_count + entre.partial_count}/${entre.total}` : "Aucun",
      label: "Compétences entrepreneuriales",
      note: "présentes dans votre profil",
      delta: null,
    },
    {
      icon: I.layers,
      value: opportunities.length,
      label: "Pistes dans votre domaine",
      note: domain ? `domaine : ${domain}` : "profil requis",
      delta: null,
    },
    {
      icon: I.landmark,
      value: data.financing_institutions.length,
      label: "Pistes de financement",
      note: "public et parapublic",
      delta: null,
    },
    {
      icon: I.users,
      value: missions.length,
      label: "Missions du marché",
      note: "premiers revenus possibles",
      delta: null,
    },
  ];

  return (
    <div className="page ent-page">
      <div className="dash-columns">
        <div className="dash-col-main">
          {/* ---------- Héros : l'agent entrepreneuriat ---------- */}
          <div className="ag-hero-wrap">
            <section className="ag-hero">
              <span className="ag-hero-mascot"><Icon d={I.bot} size={44} /></span>
              <div className="ag-hero-body">
                <div className="ag-hero-top">
                  <h1>Entrepreneuriat</h1>
                  <span className="agent-status">Actif</span>
                </div>
                <p className="ag-hero-tagline">
                  Ori, votre agent entrepreneuriat, travaille pour vous
                </p>
                <p className="ag-hero-desc">{briefing}</p>
                <div className="ag-hero-foot">
                  <a className="btn btn-primary btn-small" href="#business-plan">
                    Générer mon business plan
                  </a>
                  <a className="btn btn-ghost btn-small" href="#idees">
                    Voir les pistes de mon domaine
                  </a>
                </div>
              </div>
              <aside className="ag-quote">
                <Icon d={I.lightbulb} size={18} />
                <p>
                  « Je ne vous promets pas la réussite : je vous donne les
                  pistes, les étapes et les portes à frapper. »
                </p>
              </aside>
            </section>
          </div>

          {entre && !entre.has_profile && (
            <section className="ent-callout">
              <span className="ent-callout-icon"><Icon d={I.alert} size={18} /></span>
              <div>
                <h2>Votre profil n'est pas encore complet</h2>
                <p>
                  La guidance dans VOTRE domaine, les écarts à combler et le
                  business plan s'appuient sur votre profil validé. Les
                  financements, concours et incubateurs restent consultables
                  ci-dessous.
                </p>
              </div>
              <Link className="btn btn-primary btn-small" to="/questionnaire">
                Créer mon profil
              </Link>
            </section>
          )}

          {/* ---------- Ce que l'agent a déjà préparé ---------- */}
          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.bot} size={16} /> Ce que j'ai déjà préparé pour vous</h2>
              <span className="ent-tag">Analyse du profil réel</span>
            </div>
            <div className="ag-stats">
              {stats.map((s) => (
                <div key={s.label} className="ag-stat">
                  <div className="ag-stat-head">
                    <span className="ag-stat-icon"><Icon d={s.icon} size={16} /></span>
                    <span className="ag-stat-label">{s.label}</span>
                  </div>
                  <div className="ag-stat-value">{s.value}</div>
                  <div className="ag-stat-foot">
                    <span className="ag-stat-note">{s.note}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* ---------- Profil entrepreneurial ---------- */}
          {entre?.has_profile && (
            <section className="dash-card">
              <div className="dash-card-head">
                <h2><Icon d={I.award} size={16} /> Mon profil entrepreneurial</h2>
                <Link className="link-more" to="/profil">
                  Modifier mon profil <ArrowIcon direction="right" size={12} />
                </Link>
              </div>
              <p className="ent-lead">
                Le référentiel vient de la taxonomie de compétences
                d'OrientSkill : rien n'est inventé. Il sert à situer votre
                profil, jamais à vous noter.
              </p>

              <div className="ent-coverage">
                <div className="ent-coverage-head">
                  <span className="ent-coverage-value">{entre.coverage} %</span>
                  <span className="ent-coverage-label">
                    du référentiel entrepreneurial est couvert par les
                    compétences de votre profil
                  </span>
                </div>
                <span className="ent-coverage-track">
                  <span className="ent-coverage-fill" style={{ width: `${entre.coverage}%` }} />
                </span>
                <p className="ent-coverage-note">
                  ✓ {entre.covered_count} couverte{plural(entre.covered_count, "", "s")} ·{" "}
                  △ {entre.partial_count} partielle{plural(entre.partial_count, "", "s")} ·{" "}
                  ○ {entre.missing_count} à acquérir
                </p>
              </div>

              <div className="ent-groups">
                {groups.map((group) => <SkillGroup key={group.key} group={group} />)}
              </div>

              {acquired.length > 0 && (
                <p className="ent-note">
                  <Icon d={I.check} size={13} /> Déjà mobilisable dans votre
                  projet : {acquired.join(", ")}.
                </p>
              )}
              {missingPriority.length > 0 && (
                <p className="ent-note warn">
                  <Icon d={I.alert} size={13} /> À acquérir en priorité pour
                  porter une activité : {missingPriority.join(", ")}. Ori peut
                  vous bâtir le parcours correspondant.
                </p>
              )}

              {entre.trade_skills.length > 0 && (
                <div className="ent-trade">
                  <h3>Votre métier, votre premier capital</h3>
                  <p>
                    Ces compétences de votre profil ne figurent pas dans le
                    référentiel entrepreneurial : ce sont elles qui font la
                    différence face aux autres porteurs de projet.
                  </p>
                  <div className="ent-group-tags">
                    {entre.trade_skills.map((t) => (
                      <span className="ent-trade-tag" key={t.name}>
                        {t.name} <em>{t.category}</em>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="actions-row">
                <Link className="btn btn-outline btn-small" to="/learning">
                  Voir mon plan de progression <ArrowIcon direction="right" size={12} />
                </Link>
              </div>
            </section>
          )}

          {/* ---------- Mon domaine et mes pistes ---------- */}
          {entre?.has_profile && (
            <section className="dash-card" id="idees">
              <div className="dash-card-head">
                <h2><Icon d={I.compass} size={16} /> Comment entreprendre dans mon domaine</h2>
                {domain && <span className="ent-tag strong">{domain}</span>}
              </div>
              <p className="ent-lead">{guidance?.introduction}</p>

              {opportunities.length > 0 && (
                <>
                  <h3 className="ent-sub">Pistes à instruire, jamais garanties</h3>
                  <div className="ent-ideas">
                    {opportunities.map((idea) => (
                      <article className="ent-idea" key={idea}>
                        <span className="ent-idea-icon"><Icon d={I.lightbulb} size={15} /></span>
                        <p>{idea}</p>
                      </article>
                    ))}
                  </div>
                </>
              )}

              {steps.length > 0 && (
                <>
                  <h3 className="ent-sub">Vos premières étapes</h3>
                  <ol className="ent-steps">
                    {steps.map((step, index) => (
                      <li key={step}>
                        <span className="ent-step-num">{index + 1}</span>
                        <span>{step}</span>
                      </li>
                    ))}
                  </ol>
                </>
              )}

              <p className="ent-note">
                Pistes issues des réalités du marché camerounais : à tester avec
                de vrais clients avant d'investir. Aucune réussite n'est promise.
              </p>
            </section>
          )}

          {/* ---------- Programmes, concours et accompagnement ---------- */}
          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.layers} size={16} /> Programmes, concours et accompagnement</h2>
              <span className="ent-tag">{resources.length} répertoriés</span>
            </div>
            <div className="ent-tabs">
              <button
                type="button"
                className={`ent-tab${tab === "all" ? " active" : ""}`}
                onClick={() => setTab("all")}
              >
                Tous ({resources.length})
              </button>
              {KINDS.map((kind) => {
                const count = resources.filter((r) => r.kind === kind).length;
                return (
                  <button
                    key={kind}
                    type="button"
                    className={`ent-tab${tab === kind ? " active" : ""}`}
                    onClick={() => setTab(kind)}
                  >
                    <Icon d={KIND_ICONS[kind]} size={13} />{" "}
                    {ENTREPRENEUR_KIND_LABELS[kind]} ({count})
                  </button>
                );
              })}
            </div>
            {filtered.length === 0 ? (
              <Empty title="Aucun programme dans cette catégorie" />
            ) : (
              <div className="ent-res-list">
                {filtered.map((r) => <ResourceCard key={r.id} resource={r} />)}
              </div>
            )}
          </section>

          {/* ---------- Missions et micro-opportunités ---------- */}
          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.briefcase} size={16} /> Missions et micro-opportunités</h2>
              <Link className="link-more" to="/opportunites">
                Toutes les offres <ArrowIcon direction="right" size={12} />
              </Link>
            </div>
            <p className="ent-lead">
              Des missions freelance réellement publiées sur la plateforme :
              un moyen de tester votre activité, de vous faire connaître et de
              générer un premier revenu pendant que le projet se construit.
            </p>
            {missions.length === 0 ? (
              <Empty title="Aucune mission publiée pour l'instant" />
            ) : (
              <div className="ent-missions">
                {missions.map((job) => (
                  <Link className="ent-mission" key={job.id} to={`/opportunites/${job.id}`}>
                    <CompanyLogo
                      name={job.company}
                      logoUrl={job.company_branding?.logo_url}
                      className="opp-logo"
                    />
                    <span className="ent-mission-main">
                      <span className="ent-mission-title">{job.title}</span>
                      <span className="opp-meta">
                        {job.company} · {job.location} · {job.contract_type}
                      </span>
                    </span>
                    {job.match_score != null && (
                      <span className={`ent-mission-score ${scoreLevel(job.match_score) || ""}`}>
                        {job.match_score} % · {LEVEL_LABELS[scoreLevel(job.match_score)] || ""}
                      </span>
                    )}
                  </Link>
                ))}
              </div>
            )}
            <p className="ent-note">
              La correspondance est calculée sur votre profil : une mission peut
              valoir la peine même avec un score faible (expérience, réseau,
              revenu d'appoint).
            </p>
          </section>

          {/* ---------- Business plan ---------- */}
          <section className="dash-card" id="business-plan">
            <div className="dash-card-head">
              <h2><Icon d={I.pen} size={16} /> Construire mon business plan avec Ori</h2>
            </div>
            <p className="ent-lead">
              Vous donnez vos chiffres, Ori structure le document : activité,
              clientèle, capital disponible, localisation, plus les compétences
              réelles de votre profil. Rien n'est inventé. Complétez ensuite
              avec votre étude de marché terrain.
            </p>
            <BusinessPlanForm onCreated={(doc) => setDocuments((prev) => [doc, ...prev])} />

            <h3 className="ent-sub">Mes business plans</h3>
            {plans.length === 0 ? (
              <Empty title="Aucun business plan généré pour l'instant">
                <p className="small muted">
                  Le premier document généré apparaîtra ici et dans « Mes
                  documents », exportable en markdown ou PDF.
                </p>
              </Empty>
            ) : (
              <ul className="ent-plans">
                {plans.map((doc) => (
                  <li key={doc.id}>
                    <span className="ent-plan-icon"><Icon d={I.file} size={15} /></span>
                    <span className="ent-plan-main">
                      <span className="ent-plan-title">{doc.title}</span>
                      <span className="opp-meta">Généré le {fmtDate(doc.created_at)}</span>
                    </span>
                    <Link className="btn btn-outline btn-small" to={`/documents?open=${doc.id}`}>
                      Ouvrir
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* ---------- Barre de commande de l'agent ---------- */}
          <AssistantChat compact suggestions={ENT_SUGGESTIONS} pageContext="Entrepreneuriat" />
        </div>

        {/* ---------- Colonne latérale ---------- */}
        <div className="dash-col-side">
          <AgentSideCard
            page="Entrepreneuriat"
            hint="Ori peut auditer votre projet, votre modèle économique et les financements réels à viser."
            prompt="Comment améliorer mon profil entrepreneurial ?"
          />
          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.landmark} size={16} /> Financements à instruire</h2>
            </div>
            <ul className="ent-fin">
              {data.financing_institutions.map((inst) => (
                <li key={inst.name}>
                  <div className="ent-fin-head">
                    <span className="ent-fin-name">{inst.name}</span>
                    <span className="ent-fin-type">{inst.type}</span>
                  </div>
                  <p className="ent-fin-what">{inst.finances}</p>
                  <p className="ent-fin-cond">Conditions : {inst.conditions}</p>
                  {inst.url && (
                    <a className="link-more" href={inst.url} target="_blank" rel="noreferrer">
                      Site officiel <ArrowIcon direction="right" size={12} />
                    </a>
                  )}
                </li>
              ))}
            </ul>
            <p className="ent-note">
              C'est l'institution qui décide : aucune obtention n'est garantie.
            </p>
          </section>

          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.clipboard} size={16} /> Dossier bancaire</h2>
            </div>
            <p className="ent-lead">
              Ce que les banques et microfinances demandent généralement au
              Cameroun, dans l'ordre d'instruction.
            </p>
            <ol className="ent-bank">
              {data.bank_prep.map((item, index) => (
                <li key={item.step}>
                  <span className="ent-step-num">{index + 1}</span>
                  <span className="ent-bank-main">
                    <span className="ent-bank-step">{item.step}</span>
                    <span className="ent-bank-detail">{item.detail}</span>
                  </span>
                </li>
              ))}
            </ol>
            <a className="btn btn-outline btn-small" href="#business-plan">
              Étape 1 : générer mon business plan
            </a>
          </section>

          {nextSkills.length > 0 && (
            <section className="dash-card">
              <div className="dash-card-head">
                <h2><Icon d={I.book} size={16} /> Renforcer mon profil</h2>
                <Link className="link-more" to="/learning">
                  Mon parcours <ArrowIcon direction="right" size={12} />
                </Link>
              </div>
              <ul className="ent-skills">
                {nextSkills.map((item, index) => (
                  <li key={item.skill}>
                    <span className="ent-skill-name">{item.skill}</span>
                    {/* Même motif que l'écart précédent : on ne le répète pas. */}
                    {item.reason && item.reason !== nextSkills[index - 1]?.reason && (
                      <span className="ent-skill-reason">{item.reason}</span>
                    )}
                  </li>
                ))}
              </ul>
              <p className="ent-note">
                Compétences attendues par le marché dans votre domaine, avec les
                formations réelles disponibles.
              </p>
            </section>
          )}

          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.compass} size={16} /> Aller plus loin</h2>
            </div>
            <ul className="ent-links">
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
                <Link to="/assistant">
                  <Icon d={I.chat} size={15} /> Parler à Ori
                </Link>
              </li>
              <li>
                <Link to="/profil">
                  <Icon d={I.user} size={15} /> Mon profil
                </Link>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
