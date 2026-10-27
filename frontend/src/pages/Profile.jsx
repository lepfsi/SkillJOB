import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api, apiRaw } from "../api/client.js";
import ProfileEditor from "../components/ProfileEditor.jsx";
import CvImportDialog from "../components/CvImportDialog.jsx";
import PhotoCropDialog from "../components/PhotoCropDialog.jsx";
import Ring from "../components/Ring.jsx";
import VerifiedBadge from "../components/VerifiedBadge.jsx";
import { Icon, I, ArrowIcon } from "../components/icons.jsx";
import {
  sanitizeProfile,
  VERIFICATION_LABELS,
  PROFICIENCY_LABELS,
  SOURCE_LABELS,
  EXPERIENCE_TYPE_LABELS,
  initialsOf,
  plural,
} from "../lib.js";
import { useAuth } from "../context/AuthContext.jsx";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";

// Page « Mon profil » (maquette) : bannière d'identité, résumé compris par
// l'IA, forces / potentiel / prochaines actions, puis un aperçu détaillé
// par onglets. Tout est lu depuis l'API (§47) : aucune donnée inventée.
// Les jauges des compétences et des langues ne sont qu'une TRADUCTION
// visuelle du niveau déclaré (aucun pourcentage stocké côté serveur).

const TABS = [
  { id: "apercu", label: "Aperçu", icon: I.home },
  { id: "informations", label: "Informations", icon: I.layers },
  { id: "experience", label: "Expérience", icon: I.briefcase },
  { id: "competences", label: "Compétences", icon: I.zap },
  { id: "formation", label: "Formation", icon: I.cap },
  { id: "certifications", label: "Certifications", icon: I.award },
  { id: "projets", label: "Projets", icon: I.folder },
  { id: "preferences", label: "Préférences", icon: I.settings },
];

// Niveaux maîtrisés -> largeur de jauge (présentation, pas une donnée).
const PROFICIENCY_METER = { debutant: 40, intermediaire: 70, avance: 92 };
const LANGUAGE_METER = {
  debutant: 40,
  intermediaire: 70,
  professionnel: 80,
  courant: 90,
  avance: 90,
  bilingue: 100,
  natif: 100,
};
const PROFICIENCY_RANK = { avance: 3, intermediaire: 2, debutant: 1 };
const AVAILABILITY_LABELS = {
  "Immédiate": "Disponible immédiatement",
  "Sous 1 mois": "Disponible sous 1 mois",
  "Sous 3 mois": "Disponible sous 3 mois",
};
const MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

const EDIT_TITLES = {
  identity: "Modifier mes informations",
  experience: "Modifier mes expériences",
  skills: "Modifier mes compétences",
  education: "Modifier ma formation",
  certifications: "Modifier mes certifications",
  projects: "Modifier mes projets",
  preferences: "Modifier mes préférences",
};

const norm = (v) =>
  String(v || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();

const cleanValue = (v) => String(v ?? "").trim();

const joinFacts = (...values) => values.map(cleanValue).filter(Boolean).join(" · ");

// Fusion non destructive d'un brouillon de CV dans le profil courant. Les
// champs déjà renseignés ne sont jamais écrasés ; seuls les éléments absents
// sont proposés, puis validés dans l'éditeur avant tout PUT /api/profile.
function buildImportPlan(profile, draft) {
  const base = profile || {};
  const source = draft || {};
  const additions = [];
  const filled = [];
  const merged = { ...base };

  const scalarLabels = {
    title: "Titre professionnel",
    summary: "Résumé professionnel",
    location: "Localisation",
    mobility: "Mobilité",
    availability: "Disponibilité",
  };
  Object.entries(scalarLabels).forEach(([field, label]) => {
    if (!cleanValue(base[field]) && cleanValue(source[field])) {
      merged[field] = source[field];
      filled.push(label);
    }
  });

  function addList(field, label, keyOf, display) {
    const current = base[field] || [];
    const seen = new Set(current.map((item) => norm(keyOf(item))).filter(Boolean));
    const added = (source[field] || []).filter((item) => {
      const key = norm(keyOf(item));
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    merged[field] = current;
    if (added.length > 0) {
      merged[field] = [...current, ...added];
      additions.push({
        field,
        label,
        names: added.map(display).map(cleanValue).filter(Boolean),
      });
    }
  }

  addList(
    "experiences",
    "Expériences",
    (item) => joinFacts(item.title, item.organization, item.start_date),
    (item) => joinFacts(item.title, item.organization)
  );
  addList(
    "education",
    "Formations",
    (item) => joinFacts(item.degree, item.institution, item.end_year),
    (item) => joinFacts(item.degree, item.institution)
  );
  addList(
    "certifications",
    "Certifications",
    (item) => joinFacts(item.name, item.issuer, item.year),
    (item) => item.name
  );
  addList(
    "languages",
    "Langues",
    (item) => item.language,
    (item) => joinFacts(item.language, item.level)
  );
  addList(
    "projects",
    "Projets",
    (item) => joinFacts(item.name, item.url),
    (item) => item.name
  );
  addList(
    "skills",
    "Compétences",
    (item) => item.skill,
    (item) => item.skill
  );

  const prefs = base.preferences || {
    sectors: [], target_roles: [], contract_types: [], remote_ok: false, linkedin_url: "",
  };
  const draftPrefs = source.preferences || {};
  const mergedPrefs = { ...prefs };
  const prefNames = [];
  [
    ["sectors", "Secteurs"],
    ["target_roles", "Métiers visés"],
    ["contract_types", "Types de contrat"],
  ].forEach(([field]) => {
    const current = prefs[field] || [];
    const seen = new Set(current.map(norm));
    const added = (draftPrefs[field] || []).filter((value) => {
      const key = norm(value);
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    mergedPrefs[field] = current;
    if (added.length > 0) {
      mergedPrefs[field] = [...current, ...added];
      prefNames.push(...added);
    }
  });
  if (!prefs.remote_ok && draftPrefs.remote_ok) {
    mergedPrefs.remote_ok = true;
    prefNames.push("Télétravail accepté");
  }
  if (!cleanValue(prefs.linkedin_url) && cleanValue(draftPrefs.linkedin_url)) {
    mergedPrefs.linkedin_url = draftPrefs.linkedin_url;
    filled.push("Lien LinkedIn");
  }
  merged.preferences = mergedPrefs;
  if (prefNames.length > 0) {
    additions.push({ field: "preferences", label: "Préférences", names: prefNames });
  }

  const total = additions.reduce((sum, item) => sum + item.names.length, 0) + filled.length;
  return { merged, additions, filled, total };
}

function CvImportPreview({ entry, onApply, onDismiss }) {
  const plan = entry.plan;
  const report = entry.report || {};
  return (
    <section className="dash-card pf-import-card">
      <div className="dash-card-head">
        <h2><Icon d={I.file} size={16} /> CV analysé</h2>
        <span className="chip chip-soft">Brouillon non enregistré</span>
      </div>
      <p className="small muted pf-import-source">Source : {entry.label}</p>

      <div className="pf-import-report">
        <span><strong>{report.skills_found || 0}</strong> compétence{plural(report.skills_found || 0, "", "s")}</span>
        <span><strong>{report.experiences_found || 0}</strong> expérience{plural(report.experiences_found || 0, "", "s")}</span>
        <span><strong>{report.degrees_found || 0}</strong> formation{plural(report.degrees_found || 0, "", "s")}</span>
        <span><strong>{report.certifications_found || 0}</strong> certification{plural(report.certifications_found || 0, "", "s")}</span>
      </div>

      {plan.total === 0 ? (
        <p className="pf-import-empty-note">
          Aucun nouvel élément détecté : votre profil contient déjà ces informations.
          Vous pouvez tout de même ouvrir l'éditeur pour les vérifier.
        </p>
      ) : (
        <>
          <h3 className="pf-import-subtitle">
            {plan.total} élément{plural(plan.total, "", "s")} à ajouter après votre validation
          </h3>
          <ul className="pf-import-list">
            {plan.additions.map((addition) => (
              <li key={addition.field}>
                <strong>{addition.names.length} {addition.label.toLowerCase()}</strong>
                <span>
                  {addition.names.slice(0, 3).join(" · ")}
                  {addition.names.length > 3
                    ? ` et ${addition.names.length - 3} autre${plural(addition.names.length - 3, "", "s")}`
                    : ""}
                </span>
              </li>
            ))}
          </ul>
          {plan.filled.length > 0 && (
            <p className="pf-import-filled">
              Champs complétés : {plan.filled.join(", ")}.
            </p>
          )}
        </>
      )}

      <p className="pf-import-warning">
        Rien n'est enregistré pour l'instant. Vous pourrez corriger chaque information
        dans l'éditeur, puis cliquer sur Enregistrer.
      </p>
      <div className="actions-row">
        <button type="button" className="btn btn-outline" onClick={onDismiss}>
          Ignorer
        </button>
        <button type="button" className="btn btn-primary" onClick={onApply}>
          {plan.total === 0 ? "Ouvrir l'éditeur" : "Vérifier et compléter"}
        </button>
      </div>
    </section>
  );
}

function fmtMonth(value) {
  if (!value) return "";
  const m = String(value).match(/^(\d{4})-(\d{1,2})/);
  if (!m) return String(value);
  return `${MONTHS[Number(m[2]) - 1] || ""} ${m[1]}`.trim();
}

function fmtPeriod(start, end) {
  const a = fmtMonth(start);
  const b = end ? fmtMonth(end) : "aujourd'hui";
  return [a, b].filter(Boolean).join(" à ");
}

function fmtYears(start, end) {
  if (!start && !end) return "";
  return [start, end || "aujourd'hui"].filter(Boolean).join(" à ");
}

function Card({ icon, title, action, children, className = "" }) {
  return (
    <section className={`dash-card ${className}`.trim()}>
      <div className="dash-card-head">
        <h2>{icon && <Icon d={icon} size={16} />} {title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function SkillBar({ name, level, pct, note }) {
  return (
    <div className="pf-skill">
      <div className="pf-skill-line">
        <span className="pf-skill-name">{name}</span>
        <span className="pf-skill-level">{level}</span>
      </div>
      <div className="pf-skill-bar">
        <span className="pf-skill-fill" style={{ width: `${pct}%` }} />
      </div>
      {note && <span className="pf-skill-note">{note}</span>}
    </div>
  );
}

export default function Profile() {
  const navigate = useNavigate();
  const { user, setUser } = useAuth();
  const [profile, setProfile] = useState(undefined);
  const [careers, setCareers] = useState([]);
  const [dash, setDash] = useState(null);
  const [photoUrl, setPhotoUrl] = useState(null);
  const [photoFile, setPhotoFile] = useState(null);
  const [verifStatus, setVerifStatus] = useState("none");
  const [tab, setTab] = useState("apercu");
  const [skillTab, setSkillTab] = useState("principales");
  const [editing, setEditing] = useState(false);
  const [editSections, setEditSections] = useState(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importPreview, setImportPreview] = useState(null);
  const [showChecks, setShowChecks] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  function openEditor(sections = null) {
    setEditSections(sections);
    setEditing(true);
    setSaved(false);
    setImportPreview(null);
  }

  function closeEditor() {
    setEditing(false);
    setEditSections(null);
    setSaved(false);
  }

  function importAnalyzed(result, label) {
    setImportOpen(false);
    setImportPreview({
      ...result,
      label,
      plan: buildImportPlan(profile, result.draft),
    });
    setSaved(false);
  }

  function applyImport() {
    if (!importPreview) return;
    setProfile(importPreview.plan.merged);
    openEditor(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function reloadUser() {
    api("/auth/me").then((u) => {
      setUser(u);
      localStorage.setItem("orientskill_user", JSON.stringify(u));
      setVerifStatus(u.verification_status || "none");
      if (u.photo_path) {
        apiRaw("/profile/photo")
          .then((res) => {
            if (res.ok) return res.blob().then((b) => setPhotoUrl(URL.createObjectURL(b)));
            setPhotoUrl(null);
          })
          .catch(() => setPhotoUrl(null));
      } else {
        setPhotoUrl(null);
      }
    }).catch(() => {});
  }

  useEffect(() => {
    Promise.all([
      api("/profile").catch(() => null),
      api("/careers").catch(() => []),
      api("/dashboard").catch(() => null),
    ]).then(([p, c, d]) => {
      setProfile(p);
      setCareers(c || []);
      setDash(d);
    });
    api("/profile/verification").then((v) => setVerifStatus(v.status)).catch(() => {});
    reloadUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function choosePhoto(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError("");
    setPhotoFile(file);
  }

  async function save() {
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const updated = await api("/profile", { method: "PUT", body: sanitizeProfile(profile) });
      setProfile(updated);
      setEditing(false);
      setEditSections(null);
      setSaved(true);
      // Les scores (complétude, trajectoires) dépendent du profil : on les rafraîchit.
      Promise.all([
        api("/dashboard").catch(() => null),
        api("/careers").catch(() => []),
      ]).then(([d, c]) => {
        setDash(d);
        setCareers(c || []);
      });
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  if (profile === undefined) {
    return <div className="page"><Loader /></div>;
  }

  const verified = verifStatus === "verified";
  const completeness = dash?.profile_completeness || { score: 0, checked: [], missing: [] };
  const skillsToImprove = dash?.skills_to_improve || [];
  const skillGaps = dash?.skill_gaps?.length
    ? dash.skill_gaps
    : skillsToImprove.map((skill) => ({ skill, reason: "", source_label: "" }));
  const location = profile?.location || [user?.city, user?.region].filter(Boolean).join(", ");
  const availability = AVAILABILITY_LABELS[profile?.availability] || (profile?.availability ? `Disponibilité : ${profile.availability}` : "");

  const skills = profile?.skills || [];
  const sortedSkills = [...skills].sort(
    (a, b) => (PROFICIENCY_RANK[b.proficiency] || 0) - (PROFICIENCY_RANK[a.proficiency] || 0)
  );
  const topSkills = sortedSkills.slice(0, 4);
  const withEvidence = sortedSkills.filter((s) => s.source === "evidence");
  const listedSkills = skillTab === "preuves" ? withEvidence : sortedSkills;

  const experiences = profile?.experiences || [];
  const education = profile?.education || [];
  const certifications = profile?.certifications || [];
  const languages = profile?.languages || [];
  const projects = profile?.projects || [];
  const prefs = profile?.preferences || { sectors: [], target_roles: [], contract_types: [], remote_ok: false };
  const topCareers = careers.slice(0, 3);
  const editTitle = editSections?.length === 1
    ? (EDIT_TITLES[editSections[0]] || "Modifier mon profil")
    : "Modifier mon profil";

  // ------------------------------------------------ blocs réutilisables

  const experienceList = (items) => (
    <ul className="pf-timeline">
      {items.map((it) => (
        <li key={it.id || `${it.title}-${it.start_date}`}>
          <span className="pf-timeline-dot"><Icon d={I.briefcase} size={14} /></span>
          <div className="pf-timeline-body">
            <div className="pf-timeline-head">
              <strong>{it.title}</strong>
              <span className="chip chip-soft">{EXPERIENCE_TYPE_LABELS[it.type] || "Expérience"}</span>
            </div>
            <span className="opp-meta">
              {[it.organization, fmtPeriod(it.start_date, it.end_date)].filter(Boolean).join(" · ")}
            </span>
            {it.description && <p className="pf-timeline-text">{it.description}</p>}
            {it.skills?.length > 0 && (
              <div className="pf-chips pf-chips-tight">
                {it.skills.map((s) => <span key={s} className="chip chip-mini">{s}</span>)}
              </div>
            )}
          </div>
        </li>
      ))}
    </ul>
  );

  const skillList = (items, limit) => {
    const list = limit ? items.slice(0, limit) : items;
    if (list.length === 0) return <p className="muted small">Aucune compétence dans cette vue.</p>;
    return (
      <div className="pf-skills">
        {list.map((s) => (
          <SkillBar
            key={s.skill}
            name={s.skill}
            level={PROFICIENCY_LABELS[s.proficiency] || "Non renseigné"}
            pct={PROFICIENCY_METER[s.proficiency] || 40}
            note={SOURCE_LABELS[s.source] || ""}
          />
        ))}
      </div>
    );
  };

  const educationCards = () => (
    education.length === 0 ? <p className="muted small">Aucune formation renseignée.</p> : (
      <ul className="pf-list">
        {education.map((e) => (
          <li key={e.id || e.degree}>
            <strong>{e.degree}</strong>
            <span className="opp-meta">{[e.institution, fmtYears(e.start_year, e.end_year)].filter(Boolean).join(" · ")}</span>
            {e.field && <span className="pf-timeline-text">{e.field}</span>}
            {e.end_year && <span className="chip chip-soft">Diplôme obtenu</span>}
          </li>
        ))}
      </ul>
    )
  );

  const certificationCards = () => (
    certifications.length === 0 ? <p className="muted small">Aucune certification renseignée.</p> : (
      <ul className="pf-list">
        {certifications.map((c) => (
          <li key={c.id || c.name}>
            <strong>{c.name}</strong>
            <span className="opp-meta">{[c.issuer, c.year].filter(Boolean).join(" · ")}</span>
          </li>
        ))}
      </ul>
    )
  );

  const languageCards = () => (
    languages.length === 0 ? <p className="muted small">Aucune langue renseignée.</p> : (
      <div className="pf-skills">
        {languages.map((l) => {
          const pct = LANGUAGE_METER[norm(l.level)] || null;
          return (
            <div className="pf-skill" key={l.id || l.language}>
              <div className="pf-skill-line">
                <span className="pf-skill-name">{l.language}</span>
                <span className="pf-skill-level">{l.level || "Non renseigné"}</span>
              </div>
              {pct && (
                <div className="pf-skill-bar">
                  <span className="pf-skill-fill" style={{ width: `${pct}%` }} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    )
  );

  const projectCards = () => (
    <div className="pf-projects">
      {projects.map((p) => (
        <article className="pf-project" key={p.id || p.name}>
          <span className="pf-project-icon"><Icon d={I.folder} size={18} /></span>
          <div>
            <strong>{p.name}</strong>
            {p.skills?.length > 0 && (
              <div className="pf-chips pf-chips-tight">
                {p.skills.map((s) => <span key={s} className="chip chip-mini">{s}</span>)}
              </div>
            )}
            {p.description && <p className="pf-timeline-text">{p.description}</p>}
            {p.url && (
              <a className="link-more" href={p.url} target="_blank" rel="noreferrer">
                Voir la réalisation <ArrowIcon direction="right" />
              </a>
            )}
          </div>
        </article>
      ))}
      <button type="button" className="pf-project-add" onClick={() => openEditor(["projects"])}>
        <span className="pf-project-add-icon"><Icon d={I.plus} size={18} /></span>
        <strong>Ajouter un projet</strong>
        <span className="muted small">Montrez vos réalisations et vos projets personnels.</span>
      </button>
    </div>
  );

  const preferencesBlock = () => (
    <dl className="pf-prefs">
      <div>
        <dt><Icon d={I.clipboard} size={14} /> Type de contrat</dt>
        <dd>{prefs.contract_types?.length ? prefs.contract_types.join(" / ") : "Non renseigné"}</dd>
      </div>
      <div>
        <dt><Icon d={I.pin} size={14} /> Mobilité</dt>
        <dd>{profile?.mobility || "Non renseignée"}</dd>
      </div>
      <div>
        <dt><Icon d={I.globe} size={14} /> Télétravail</dt>
        <dd>{prefs.remote_ok ? "Accepté" : "Non accepté"}</dd>
      </div>
      <div>
        <dt><Icon d={I.compass} size={14} /> Secteurs préférés</dt>
        <dd>{prefs.sectors?.length ? prefs.sectors.join(", ") : "Non renseignés"}</dd>
      </div>
    </dl>
  );

  const objectivesBlock = () => (
    <ul className="pf-objectives">
      {prefs.target_roles?.length ? (
        prefs.target_roles.map((r) => <li key={r}>« {r} »</li>)
      ) : (
        <li className="muted">Aucun métier visé pour l'instant.</li>
      )}
    </ul>
  );

  // ------------------------------------------------------------- onglets

  function tabContent() {
    if (tab === "informations") {
      return (
        <>
          <Card icon={I.layers} title="Informations personnelles" action={
            <button type="button" className="link-more" onClick={() => openEditor(["identity"])}>Modifier <ArrowIcon direction="right" /></button>
          }>
            <dl className="pf-prefs pf-prefs-wide">
              <div><dt><Icon d={I.user} size={14} /> Nom</dt><dd>{user?.full_name}</dd></div>
              <div><dt><Icon d={I.mail} size={14} /> Email</dt><dd>{user?.email}</dd></div>
              <div><dt><Icon d={I.pin} size={14} /> Localisation</dt><dd>{location || "Non renseignée"}</dd></div>
              <div><dt><Icon d={I.compass} size={14} /> Mobilité</dt><dd>{profile?.mobility || "Non renseignée"}</dd></div>
              <div><dt><Icon d={I.clock} size={14} /> Disponibilité</dt><dd>{profile?.availability || "Non renseignée"}</dd></div>
              <div><dt><Icon d={I.shield} size={14} /> Vérification</dt><dd>{VERIFICATION_LABELS[verifStatus] || "Non vérifié"}</dd></div>
            </dl>
          </Card>
          {profile?.summary && (
            <Card icon={I.spark} title="Résumé professionnel">
              <p className="pf-text">{profile.summary}</p>
            </Card>
          )}
          <Card icon={I.chart} title="Complétude du profil">
            <p className="pf-text">
              Votre profil est à <strong>{completeness.score}%</strong>.
              {completeness.missing.length > 0
                ? ` ${completeness.missing.length} élément${plural(completeness.missing.length, "", "s")} peu${plural(completeness.missing.length, "t", "vent")} encore améliorer votre visibilité auprès des recruteurs.`
                : " Votre profil est complet."}
            </p>
            <ul className="pf-checks">
              {completeness.checked.map((c) => (
                <li key={c.key} className={c.done ? "done" : ""}>
                  <Icon d={c.done ? I.check : I.alert} size={13} /> {c.label}
                </li>
              ))}
            </ul>
          </Card>
        </>
      );
    }

    if (tab === "experience") {
      return (
        <Card icon={I.briefcase} title="Mes expériences" action={
          <button type="button" className="link-more" onClick={() => openEditor(["experience"])}>Modifier <ArrowIcon direction="right" /></button>
        }>
          <p className="small muted">
            Expériences formelles, missions, stages et activités informelles : tout compte dans le matching.
          </p>
          {experiences.length === 0
            ? <p className="muted small">Aucune expérience renseignée.</p>
            : experienceList(experiences)}
        </Card>
      );
    }

    if (tab === "competences") {
      return (
        <Card icon={I.zap} title="Mes compétences" action={
          <button type="button" className="link-more" onClick={() => openEditor(["skills"])}>Modifier <ArrowIcon direction="right" /></button>
        }>
          <div className="pf-subtabs">
            <button type="button" className={skillTab === "principales" ? "active" : ""} onClick={() => setSkillTab("principales")}>
              Principales ({skills.length})
            </button>
            <button type="button" className={skillTab === "preuves" ? "active" : ""} onClick={() => setSkillTab("preuves")}>
              Avec preuves ({withEvidence.length})
            </button>
          </div>
          {skillList(listedSkills)}
        </Card>
      );
    }

    if (tab === "formation") {
      return (
        <Card icon={I.cap} title="Ma formation" action={
          <button type="button" className="link-more" onClick={() => openEditor(["education"])}>Modifier <ArrowIcon direction="right" /></button>
        }>
          {educationCards()}
        </Card>
      );
    }

    if (tab === "certifications") {
      return (
        <Card icon={I.award} title="Mes certifications" action={
          <button type="button" className="link-more" onClick={() => openEditor(["certifications"])}>Modifier <ArrowIcon direction="right" /></button>
        }>
          {certificationCards()}
        </Card>
      );
    }

    if (tab === "projets") {
      return (
        <Card icon={I.folder} title="Mes projets & portfolio" action={
          <button type="button" className="link-more" onClick={() => openEditor(["projects"])}>Modifier <ArrowIcon direction="right" /></button>
        }>
          <p className="small muted">Des réalisations concrètes qui prouvent vos compétences.</p>
          {projectCards()}
        </Card>
      );
    }

    if (tab === "preferences") {
      return (
        <>
          <Card icon={I.target} title="Mes objectifs professionnels" action={
            <button type="button" className="link-more" onClick={() => openEditor(["preferences"])}>Modifier <ArrowIcon direction="right" /></button>
          }>
            {objectivesBlock()}
          </Card>
          <Card icon={I.settings} title="Mes préférences" action={
            <button type="button" className="link-more" onClick={() => openEditor(["preferences"])}>Modifier <ArrowIcon direction="right" /></button>
          }>
            {preferencesBlock()}
          </Card>
        </>
      );
    }

    // Aperçu (par défaut)
    return (
      <>
        <div className="pf-row-2">
          <Card icon={I.briefcase} title="Mon parcours professionnel" action={
            <button type="button" className="link-more" onClick={() => setTab("experience")}>
              Voir tout le parcours <ArrowIcon direction="right" />
            </button>
          }>
            <p className="small muted">Un aperçu de votre parcours et de vos atouts.</p>
            {experiences.length === 0
              ? <p className="muted small">Aucune expérience renseignée.</p>
              : experienceList(experiences.slice(0, 3))}
          </Card>

          <Card icon={I.zap} title="Mes compétences" action={
            <button type="button" className="link-more" onClick={() => setTab("competences")}>
              Voir toutes <ArrowIcon direction="right" />
            </button>
          }>
            <div className="pf-subtabs">
              <button type="button" className={skillTab === "principales" ? "active" : ""} onClick={() => setSkillTab("principales")}>
                Principales
              </button>
              <button type="button" className={skillTab === "preuves" ? "active" : ""} onClick={() => setSkillTab("preuves")}>
                Avec preuves
              </button>
            </div>
            {skillList(listedSkills, 5)}
          </Card>
        </div>

        <div className="pf-row-3">
          <Card icon={I.cap} title="Ma formation">{educationCards()}</Card>
          <Card icon={I.award} title="Mes certifications">{certificationCards()}</Card>
          <Card icon={I.globe} title="Mes langues">{languageCards()}</Card>
        </div>

        <Card icon={I.folder} title="Mes projets & portfolio">
          <p className="small muted">Des réalisations concrètes qui prouvent vos compétences.</p>
          {projectCards()}
        </Card>

        <div className="pf-row-2">
          <Card icon={I.target} title="Mes objectifs professionnels">{objectivesBlock()}</Card>
          <Card icon={I.settings} title="Mes préférences">{preferencesBlock()}</Card>
        </div>
      </>
    );
  }

  // ------------------------------------------------------------------ vue

  if (profile === null) {
    return (
      <div className="page profile-page">
        <h1>Mon profil</h1>
        <p className="page-lead">
          La source de vérité de la plateforme. Le système ne génère jamais
          d'information qui ne figure pas ici.
        </p>
        <Empty title="Aucun profil pour le moment">
          <p>Construisez votre profil professionnel pour activer les recommandations.</p>
          <button className="btn btn-primary" onClick={() => navigate("/onboarding")}>
            Construire mon profil
          </button>
        </Empty>
      </div>
    );
  }

  return (
    <div className="page profile-page">
      {/* ---------------- Bannière d'identité ---------------- */}
      <section className="pf-hero">
        <div className="pf-cover" aria-hidden="true"><span className="pf-cover-glow" /></div>
        <div className="pf-hero-grid">
          <div className="pf-avatar">
            {photoUrl
              ? <img src={photoUrl} alt={user?.full_name || "Photo de profil"} />
              : <span className="pf-avatar-initials">{initialsOf(user?.full_name)}</span>}
            <label className="pf-avatar-add" title="Changer la photo de profil">
              <Icon d={I.camera} size={15} />
              <input type="file" accept=".jpg,.jpeg,.png,.webp" onChange={choosePhoto} />
            </label>
          </div>

          <div className="pf-id">
            <div className="pf-name-row">
              <h1>{user?.full_name}</h1>
              {verified && <VerifiedBadge size={20} />}
            </div>
            <p className="pf-title">{profile?.title || "Titre professionnel à renseigner"}</p>
            <div className="pf-meta">
              {location && <span><Icon d={I.pin} size={14} /> {location}</span>}
              {availability && <span className="pf-avail"><span className="pf-dot" /> {availability}</span>}
              {profile?.mobility && <span><Icon d={I.compass} size={14} /> Mobilité : {profile.mobility}</span>}
            </div>
            {topSkills.length > 0 && (
              <div className="pf-chips">
                {topSkills.map((s) => <span key={s.skill} className="chip chip-soft">{s.skill}</span>)}
              </div>
            )}
          </div>

          <aside className="pf-score">
            <div className="pf-score-top">
              <Ring score={completeness.score} text={`${completeness.score}%`} size={82} stroke={8} />
              <div className="pf-score-body">
                <span className="pf-score-label">Profil</span>
                <strong className="pf-score-title">Force du profil</strong>
                <button type="button" className="link-more" onClick={() => setShowChecks((v) => !v)}>
                  Voir le détail <ArrowIcon direction="right" />
                </button>
              </div>
            </div>
            <button type="button" className="btn btn-primary pf-score-btn" onClick={() => openEditor(null)}>
              <Icon d={I.pen} size={14} /> Améliorer mon profil
            </button>
            <button type="button" className="btn btn-outline pf-score-btn pf-import-trigger" onClick={() => setImportOpen(true)}>
              <Icon d={I.file} size={14} /> Importer un CV
            </button>
          </aside>
        </div>

        {showChecks && (
          <div className="pf-checks-panel">
            <ul className="pf-checks">
              {completeness.checked.map((c) => (
                <li key={c.key} className={c.done ? "done" : ""}>
                  <Icon d={c.done ? I.check : I.alert} size={13} /> {c.label}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {saved && <div className="alert alert-success">Profil enregistré.</div>}
      <ErrorNote error={error} />

      {!editing && importPreview && (
        <CvImportPreview
          entry={importPreview}
          onApply={applyImport}
          onDismiss={() => setImportPreview(null)}
        />
      )}

      {editing ? (
        <>
          <div className="pf-edit-bar">
            <h2>{editTitle}</h2>
            <div className="actions-row">
              <button className="btn btn-outline" onClick={closeEditor}>Fermer</button>
              <button className="btn btn-primary" onClick={save} disabled={busy}>
                {busy ? "Enregistrement…" : "Enregistrer"}
              </button>
            </div>
          </div>
          <ProfileEditor profile={profile} onChange={setProfile} sections={editSections} />
          <div className="actions-row">
            <button className="btn btn-primary" onClick={save} disabled={busy}>
              {busy ? "Enregistrement…" : "Enregistrer les modifications"}
            </button>
          </div>
        </>
      ) : (
        <>
          {/* ---------------- Regard de l'agent (remplace le résumé statique) ---------------- */}
          {profile?.summary && (
            <section className="pf-insight">
              <span className="pf-insight-icon"><Icon d={I.bot} size={20} /></span>
              <div className="pf-insight-body">
                <h2>{dash?.ai_label || "Ce que votre agent comprend de vous"}</h2>
                {dash?.ai_briefing ? (
                  <p className="pf-insight-text">{dash.ai_briefing}</p>
                ) : (
                  <p className="pf-insight-text">{profile.summary}</p>
                )}
                <Link className="btn btn-outline btn-small" to="/assistant">
                  Discuter avec l'agent <ArrowIcon direction="right" size={11} />
                </Link>
              </div>
            </section>
          )}

          {/* ---------------- Forces / potentiel / actions ---------------- */}
          <section className="pf-trio">
            <div className="pf-trio-card">
              <div className="pf-trio-head">
                <span className="pf-trio-icon pf-tone-green"><Icon d={I.check} size={15} /></span>
                <h3>Vos forces</h3>
              </div>
              {topSkills.length > 0 ? (
                <div className="pf-chips">
                  {sortedSkills.slice(0, 5).map((s) => (
                    <span key={s.skill} className="chip chip-soft">
                      {s.skill} · {PROFICIENCY_LABELS[s.proficiency] || "Non renseigné"}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="muted small">Aucune compétence renseignée.</p>
              )}
            </div>

            <div className="pf-trio-card">
              <div className="pf-trio-head">
                <span className="pf-trio-icon pf-tone-violet"><Icon d={I.target} size={15} /></span>
                <h3>Votre potentiel</h3>
              </div>
              <p className="pf-trio-sub">
                {topCareers.length > 0
                  ? `${topCareers.length} trajectoire${plural(topCareers.length, "", "s")} identifiée${plural(topCareers.length, "", "s")}`
                  : "Pas encore de trajectoire calculée"}
              </p>
              {topCareers.length > 0 && (
                <ol className="pf-careers">
                  {topCareers.map((c, i) => (
                    <li key={c.id}>
                      <span className="pf-rank">{i + 1}</span>
                      <span className="pf-career-title">{c.title}</span>
                      <span className="pf-career-score">{c.match.score}%</span>
                    </li>
                  ))}
                </ol>
              )}
              <Link className="link-more" to="/carriere">
                Explorer les métiers <ArrowIcon direction="right" />
              </Link>
            </div>

            <div className="pf-trio-card">
              <div className="pf-trio-head">
                <span className="pf-trio-icon pf-tone-blue"><Icon d={I.zap} size={15} /></span>
                <h3>Prochaines actions</h3>
              </div>
              {skillGaps.length > 0 ? (
                <>
                  <p className="pf-trio-sub">En renforçant vos compétences sur :</p>
                  <ul className="pf-action-list">
                    {skillGaps.slice(0, 4).map((gap) => (
                      <li key={gap.skill} title={gap.reason || ""}>
                        <Icon d={I.check} size={13} /> {gap.skill}
                        {gap.source_label && (
                          <span className="small muted"> · {gap.source_label}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="muted small">Aucune action prioritaire identifiée.</p>
              )}
              <Link className="btn btn-primary btn-small" to="/learning">
                Voir mon plan d'amélioration <ArrowIcon direction="right" size={12} />
              </Link>
            </div>
          </section>

          {/* ---------------- Onglets ---------------- */}
          <nav className="pf-tabs" role="tablist">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                className={`pf-tab${tab === t.id ? " active" : ""}`}
                onClick={() => setTab(t.id)}
              >
                <Icon d={t.icon} size={15} /> {t.label}
              </button>
            ))}
          </nav>

          <div className="dash-columns">
            <div className="dash-col-main">{tabContent()}</div>
            <div className="dash-col-side">
              <section className="pf-assistant">
                <div className="pf-assistant-head">
                  <span className="pf-assistant-icon"><Icon d={I.bot} size={17} /></span>
                  <h3>Assistant IA</h3>
                </div>
                <p className="pf-assistant-lead">Un conseil pour la suite ?</p>
                <p>Découvrez comment améliorer votre profil et accéder aux meilleures opportunités.</p>
                <Link className="btn btn-primary btn-small" to="/agent">
                  Poser une question <ArrowIcon direction="right" size={12} />
                </Link>
              </section>

              <Card icon={I.shield} title="Vérification du profil">
                <p className={`pf-verif ${verifStatus}`}>
                  <Icon d={verified ? I.check : I.alert} size={14} />
                  {VERIFICATION_LABELS[verifStatus] || "Non vérifié"}
                </p>
                <p className="small muted">
                  Une identité vérifiée renforce la confiance des recruteurs.
                </p>
                <Link className="btn btn-outline btn-small" to="/parametres-compte">
                  Gérer la vérification
                </Link>
              </Card>

              <section className="pf-quote">
                <Icon d={I.spark} size={18} />
                <p>« Chaque compétence acquise est une porte vers de nouvelles opportunités. »</p>
                <span>OrientSkill AI</span>
              </section>
            </div>
          </div>

          {/* ---------------- Barre de complétude ---------------- */}
          <section className="pf-footer-bar">
            <span className="pf-footer-icon"><Icon d={I.chart} size={18} /></span>
            <div className="pf-footer-body">
              <strong>Votre profil est à {completeness.score}%</strong>
              <span className="small muted">
                {completeness.missing.length > 0
                  ? `${completeness.missing.length} élément${plural(completeness.missing.length, "", "s")} peu${plural(completeness.missing.length, "t", "vent")} encore améliorer votre visibilité auprès des recruteurs.`
                  : "Tous les éléments clés sont renseignés."}
              </span>
            </div>
            <button type="button" className="btn btn-outline btn-small" onClick={() => setShowChecks((v) => !v)}>
              {showChecks ? "Masquer le détail" : "Voir les détails"}
            </button>
          </section>
          {showChecks && (
            <ul className="pf-checks">
              {completeness.checked.map((c) => (
                <li key={c.key} className={c.done ? "done" : ""}>
                  <Icon d={c.done ? I.check : I.alert} size={13} /> {c.label}
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      <CvImportDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onAnalyzed={importAnalyzed}
      />

      {photoFile && (
        <PhotoCropDialog
          file={photoFile}
          onClose={() => setPhotoFile(null)}
          onDone={() => {
            setPhotoFile(null);
            reloadUser();
          }}
        />
      )}
    </div>
  );
}
