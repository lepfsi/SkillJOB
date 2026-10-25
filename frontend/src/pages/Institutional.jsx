import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { plural } from "../lib.js";
import { Icon, I, ArrowIcon } from "../components/icons.jsx";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";
import AssistantChat from "../components/AssistantChat.jsx";

// Programmes publics camerounais : concours et examens, FNE, MINFOP,
// MINPME, organisés PAR INSTITUTION, puis PAR DISPOSITIF (sous-catégorie).
//
// Chaque fiche énonce son éligibilité, son calendrier annoncé et le lien
// du site officiel. Rien n'est inventé : les calendriers restent ceux
// publiés par les administrations concernées. Les PDF joints (avis,
// communiqués) sont déposés par l'administration dans la console ; la
// page se contente de les afficher et de les télécharger tels quels.

const INST_META = {
  minfopra: {
    short: "MINFOPRA",
    title: "Fonction publique : MINFOPRA",
    icon: I.landmark,
    tone: "green",
    intro:
      "Concours directs et concours d'intégration de la fonction publique : " +
      "les sessions sont publiées par le ministère.",
  },
  minesup: {
    short: "MINESUP",
    title: "Enseignement supérieur : MINESUP",
    icon: I.cap,
    tone: "blue",
    intro:
      "Universités d'État, écoles et instituts de chaque université, " +
      "avis de concours des grandes écoles.",
  },
  minefop: {
    short: "MINEFOP",
    title: "Emploi et formation : MINEFOP",
    icon: I.briefcase,
    tone: "orange",
    intro:
      "Les offres emplois et stages du Fonds National de l'Emploi (FNE), " +
      "et les bourses de formation professionnelle.",
  },
  ong: {
    short: "ONG",
    title: "ONG et organisations internationales",
    icon: I.users,
    tone: "violet",
    intro:
      "Offres d'emploi et programmes de stage des ONG présentes au " +
      "Cameroun, projet par projet.",
  },
  mindef: {
    short: "MINDEF",
    title: "Défense : MINDEF",
    icon: I.shield,
    tone: "slate",
    intro:
      "Concours et recrutements : armée, Gendarmerie, BIR, Garde " +
      "présidentielle, EMIA, armées étrangères.",
  },
  dgsn: {
    short: "DGSN",
    title: "Police nationale : DGSN",
    icon: I.award,
    tone: "bordeaux",
    intro:
      "Concours d'entrée à la police nationale, publiés par la Délégation " +
      "Générale à la Sûreté Nationale.",
  },
  appels_projets: {
    short: "Appels à projets",
    title: "Appels à projets des ministères",
    icon: I.lightbulb,
    tone: "teal",
    intro:
      "Financements et appuis publiés par les départements ministériels : " +
      "agriculture, jeunesse, tourisme, forêts, médias.",
  },
};

// Ordre de lecture : les institutions, puis les appels à projets.
const INST_ORDER = [
  "minfopra", "minesup", "minefop", "ong", "mindef", "dgsn",
  "appels_projets",
];

const PROGRAMS_SUGGESTIONS = [
  "Comment préparer un concours de la fonction publique ?",
  "Quelles bourses de formation professionnelle ?",
  "Quels concours de police ou d'armée ?",
  "Comment financer mon projet ?",
];

// ------------------------------------------------------------------- fiche

function DocumentsList({ documents }) {
  if (!documents || documents.length === 0) return null;
  return (
    <div className="prog-docs" aria-label="Documents officiels à télécharger">
      {documents.map((doc) => (
        <a
          className="prog-doc"
          key={doc.key || doc.url}
          href={doc.url}
          download={`${doc.label || "document"}.pdf`}
          title={`Télécharger « ${doc.label} » (PDF)`}
        >
          <span className="prog-doc-icon"><Icon d={I.file} size={14} /></span>
          <span className="prog-doc-label">{doc.label}</span>
          <span className="prog-doc-type">PDF</span>
        </a>
      ))}
    </div>
  );
}

function ProgramRow({ item }) {
  const docs = item.documents || [];
  return (
    <article className="prog-row">
      <div className="prog-row-head">
        <h4>{item.title}</h4>
        {item.deadline && (
          <span className="prog-deadline">
            <Icon d={I.clock} size={12} /> {item.deadline}
          </span>
        )}
      </div>
      {item.description && <p className="prog-desc">{item.description}</p>}
      {item.eligibility && (
        <p className="prog-elig">
          <span className="prog-elig-label">Éligibilité</span>
          <span>{item.eligibility}</span>
        </p>
      )}
      <DocumentsList documents={docs} />
      {item.url && (
        <div className="prog-actions">
          <a
            className="btn btn-outline btn-small"
            href={item.url}
            target="_blank"
            rel="noreferrer"
          >
            Site officiel <ArrowIcon direction="right" size={11} />
          </a>
        </div>
      )}
    </article>
  );
}

// Explorateur MINESUP : d'abord les universités d'État, puis les grandes
// écoles et concours de l'université choisie. La hiérarchie vient du
// référentiel éditable dans la console admin, jamais d'un texte deviné.
function MinesupExplorer({ universities }) {
  const [selectedSlug, setSelectedSlug] = useState("");
  const [query, setQuery] = useState("");

  const needle = query.trim().toLowerCase();
  const matches = (values) => values
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
    .includes(needle);

  const filteredUniversities = useMemo(() => {
    return universities
      .map((university) => {
        const schools = (university.schools || []).filter((school) => (
          !needle
          || matches([
            school.name, school.short_name, school.kind, school.admission,
            school.eligibility,
          ])
        ));
        const universityMatches = !needle || matches([
          university.name, university.short_name, university.city,
          university.region, university.description,
        ]);
        return {
          ...university,
          schools,
          visible: universityMatches || schools.length > 0,
        };
      })
      .filter((university) => university.visible);
  }, [universities, needle]);

  const selected = universities.find(
    (university) => university.slug === selectedSlug,
  ) || null;
  const selectedSchools = selected
    ? (selected.schools || []).filter((school) => (
      !needle || matches([
        school.name, school.short_name, school.kind, school.admission,
        school.eligibility,
      ])
    ))
    : [];
  const totalSchools = universities.reduce(
    (sum, university) => sum + (university.schools || []).length,
    0,
  );
  const regions = new Set(
    universities.map((university) => university.region).filter(Boolean),
  ).size;

  return (
    <div className="minesup-shell">
      <header className="minesup-head">
        <div>
          <span className="minesup-eyebrow">Explorateur MINESUP</span>
          <h2>{selected ? selected.name : "Les universités d'État du Cameroun"}</h2>
          <p>
            {selected
              ? "Grandes écoles, instituts et voies d'admission rattachés à cette université."
              : "Choisissez une université pour découvrir ses grandes écoles et leurs concours d'entrée."}
          </p>
        </div>
        <label className="minesup-search">
          <Icon d={I.search} size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Rechercher une université, une école, un concours…"
            aria-label="Rechercher dans l'explorateur MINESUP"
          />
          {query && (
            <button
              type="button"
              className="minesup-search-clear"
              onClick={() => setQuery("")}
              title="Effacer la recherche"
            >
              ×
            </button>
          )}
        </label>
      </header>

      {!selected && (
        <>
          <div className="minesup-stats">
            <span><strong>{universities.length}</strong> universités</span>
            <span><strong>{totalSchools}</strong> écoles et concours</span>
            <span><strong>{regions}</strong> régions couvertes</span>
            <span className="minesup-source-tag">
              <Icon d={I.link} size={12} /> Source MINESUP
            </span>
          </div>

          <div className="minesup-hint">
            <Icon d={I.cap} size={18} />
            <p>
              Sélectionnez une université pour afficher ses écoles. Chaque
              fiche indique la voie d'admission, l'éligibilité annoncée et le
              calendrier publié par le ministère.
            </p>
          </div>

          {filteredUniversities.length === 0 ? (
            <Empty title="Aucune université ne correspond">
              <p>Essayez le nom d'une école, d'une ville ou d'un concours.</p>
            </Empty>
          ) : (
            <div className="minesup-grid">
              {filteredUniversities.map((university) => (
                <button
                  type="button"
                  className="minesup-uni"
                  key={university.slug}
                  onClick={() => setSelectedSlug(university.slug)}
                >
                  <span className="minesup-uni-top">
                    <span className="minesup-monogram">
                      {university.short_name || university.name.slice(0, 2)}
                    </span>
                    <span className="minesup-uni-badge">Université d'État</span>
                  </span>
                  <span className="minesup-uni-name">{university.name}</span>
                  {(university.city || university.region) && (
                    <span className="minesup-uni-meta">
                      <Icon d={I.pin} size={12} />
                      {[university.city, university.region].filter(Boolean).join(" · ")}
                    </span>
                  )}
                  {university.description && (
                    <span className="minesup-uni-desc">
                      {university.description}
                    </span>
                  )}
                  <span className="minesup-uni-foot">
                    <span>
                      {(university.schools || []).length} école
                      {plural((university.schools || []).length, "", "s")}
                    </span>
                    <span className="minesup-uni-open">
                      Ouvrir <ArrowIcon direction="right" size={11} />
                    </span>
                  </span>
                </button>
              ))}
            </div>
          )}
        </>
      )}

      {selected && (
        <div className="minesup-detail">
          <div className="minesup-detail-bar">
            <button
              type="button"
              className="btn btn-ghost btn-small"
              onClick={() => setSelectedSlug("")}
            >
              ← Toutes les universités
            </button>
            <span className="minesup-detail-region">
              <Icon d={I.pin} size={12} />
              {[selected.city, selected.region].filter(Boolean).join(" · ")}
            </span>
          </div>

          <header className="minesup-uni-hero">
            <span className="minesup-monogram is-large">
              {selected.short_name || selected.name.slice(0, 2)}
            </span>
            <div className="minesup-uni-hero-copy">
              <span className="minesup-eyebrow">Université d'État</span>
              <h2>{selected.name}</h2>
              {selected.description && <p>{selected.description}</p>}
              {selected.source_url && (
                <a
                  className="minesup-official"
                  href={selected.source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  <Icon d={I.link} size={12} /> Site officiel du MINESUP
                </a>
              )}
            </div>
            <div className="minesup-uni-hero-stats">
              <span><strong>{selected.schools.length}</strong> écoles</span>
              <span><strong>{selectedSchools.length}</strong> affichées</span>
            </div>
          </header>

          <div className="minesup-schools-head">
            <div>
              <h3>Grandes écoles et concours</h3>
              <p className="small muted">
                {selectedSchools.length} fiche{plural(selectedSchools.length, "", "s")}
                {needle ? " correspondant à votre recherche" : " rattachées à cette université"}
              </p>
            </div>
            <span className="minesup-schools-source">
              <Icon d={I.file} size={12} /> Calendriers publiés par le MINESUP
            </span>
          </div>

          {selectedSchools.length === 0 ? (
            <Empty title="Aucune école ne correspond">
              <p>Effacez la recherche pour retrouver toutes les écoles de cette université.</p>
            </Empty>
          ) : (
            <div className="minesup-schools">
              {selectedSchools.map((school) => (
                <article className="minesup-school" key={school.id}>
                  <header className="minesup-school-head">
                    <span className="minesup-school-icon">
                      <Icon d={school.kind?.includes("Institut") ? I.layers : I.cap} size={19} />
                    </span>
                    <div>
                      <span className="minesup-school-kind">{school.kind}</span>
                      <h4>{school.name}</h4>
                      {school.short_name && (
                        <span className="minesup-school-short">{school.short_name}</span>
                      )}
                    </div>
                  </header>
                  <dl className="minesup-school-facts">
                    {school.admission && (
                      <div>
                        <dt>Admission</dt>
                        <dd>{school.admission}</dd>
                      </div>
                    )}
                    {school.eligibility && (
                      <div>
                        <dt>Éligibilité</dt>
                        <dd>{school.eligibility}</dd>
                      </div>
                    )}
                    {school.deadline && (
                      <div>
                        <dt>Calendrier</dt>
                        <dd><Icon d={I.clock} size={12} /> {school.deadline}</dd>
                      </div>
                    )}
                  </dl>
                  <footer className="minesup-school-foot">
                    {school.url ? (
                      <a
                        className="btn btn-outline btn-small"
                        href={school.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Site officiel <ArrowIcon direction="right" size={11} />
                      </a>
                    ) : (
                      <span className="small muted">Lien officiel à compléter par l'administration.</span>
                    )}
                  </footer>
                </article>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function InstitutionGroup({ group }) {
  return (
    <div className="inst-group">
      <div className="inst-group-head">
        <h3>{group.label}</h3>
        <span>
          {group.items.length} fiche{plural(group.items.length, "", "s")}
        </span>
      </div>
      <div className="inst-rows">
        {group.items.map((item) => <ProgramRow key={item.id} item={item} />)}
      </div>
    </div>
  );
}

// Carte-annuaire d'une institution (vue « Tout »).
function InstitutionCard({ section, onOpen }) {
  const { meta, groups, count } = section;
  const docs = groups.reduce(
    (sum, g) => sum + g.items.reduce((n, i) => n + (i.documents || []).length, 0),
    0,
  );
  return (
    <article className={`inst-dir tone-${meta.tone}`}>
      <div className="inst-dir-head">
        <span className="inst-dir-icon"><Icon d={meta.icon} size={20} /></span>
        <div>
          <h3>{meta.short}</h3>
          <p>{meta.title}</p>
        </div>
        <span className="inst-dir-count">{count}</span>
      </div>
      <p className="inst-dir-intro">{meta.intro}</p>
      <div className="inst-devices">
        {groups.map((g) => (
          <span className="inst-device" key={g.key}>
            {g.label} <b>{g.items.length}</b>
          </span>
        ))}
      </div>
      <div className="inst-dir-foot">
        <span className="small muted">
          {count} programme{plural(count, "", "s")}
          {docs > 0 && ` · ${docs} PDF joint${plural(docs, "", "s")}`}
        </span>
        <button
          type="button"
          className="btn btn-outline btn-small"
          onClick={() => onOpen(meta.key)}
        >
          Voir les programmes <ArrowIcon direction="right" size={11} />
        </button>
      </div>
    </article>
  );
}

// ------------------------------------------------------------------- page

export default function Institutional() {
  const [items, setItems] = useState(null);
  const [minesup, setMinesup] = useState(null);
  const [error, setError] = useState("");
  const [active, setActive] = useState("all");
  const contentRef = useRef(null);

  useEffect(() => {
    api("/institutional").then(setItems).catch((e) => setError(e.detail));
    // Catalogue MINESUP à deux niveaux : universités puis écoles. Il est
    // indépendant des fiches de concours pour rester éditable dans l'admin.
    api("/institutional/minesup")
      .then(setMinesup)
      .catch(() => setMinesup([]));
  }, []);

  // Institutions dans l'ordre de lecture, chacune sous-divisée par
  // dispositif (l'ordre de rencontre dans le référentiel est conservé).
  const sections = useMemo(() => {
    if (!items) return [];
    return INST_ORDER
      .map((category) => {
        const catItems = items.filter((i) => i.category === category);
        const groups = [];
        const seen = new Map();
        catItems.forEach((i) => {
          const key = i.subcategory || "autre";
          if (!seen.has(key)) {
            seen.set(key, {
              key,
              label: i.subcategory_label || key,
              items: [],
            });
            groups.push(seen.get(key));
          }
          seen.get(key).items.push(i);
        });
        const meta = { ...INST_META[category], key: category };
        return { category, meta, groups, count: catItems.length };
      })
      .filter((s) => s.count > 0);
  }, [items]);

  if (error && !items) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!items) {
    return <div className="page"><Loader /></div>;
  }

  const selected = active === "all"
    ? null
    : sections.find((s) => s.category === active) || null;

  const concoursCount = items.filter((i) => /concours|examen/i.test(i.title)).length;
  const dispositifs = new Set(items.map((i) => i.subcategory || "autre")).size;
  const pdfCount = items.reduce((n, i) => n + (i.documents || []).length, 0);

  const stats = [
    {
      tone: "green", icon: I.landmark, num: items.length,
      label: `programme${plural(items.length, "", "s")} référencé${plural(items.length, "", "s")}`,
      note: "concours, emplois, bourses, appels à projets",
    },
    {
      tone: "violet", icon: I.users, num: sections.length,
      label: `famille${plural(sections.length, "", "s")} de programmes`,
      note: "une par institution publique",
    },
    {
      tone: "blue", icon: I.clipboard, num: concoursCount,
      label: `concours et examen${plural(concoursCount, "", "s")}`,
      note: "fonction publique, grandes écoles, armées, police",
    },
    {
      tone: "orange", icon: I.layers, num: dispositifs,
      label: `dispositif${plural(dispositifs, "", "s")} distinct${plural(dispositifs, "", "s")}`,
      note: pdfCount > 0
        ? `${pdfCount} document${plural(pdfCount, "", "s")} PDF joint${plural(pdfCount, "", "s")}`
        : "emplois, stages, bourses, recrutements",
    },
  ];

  function openInstitution(category) {
    setActive(category);
    window.setTimeout(() => {
      contentRef.current?.scrollIntoView({ block: "start" });
    }, 40);
  }

  return (
    <div className="page inst-page">
      {/* ---------- Bandeau ---------- */}
      <section className="home-hero inst-hero">
        <div className="inst-hero-copy">
          <span className="inst-eyebrow">Administrations camerounaises</span>
          <h1>Programmes publics</h1>
          <p className="inst-hero-lead">
            Concours, emplois, bourses, stages et appels à projets,
            organisés par institution, puis par dispositif.
          </p>
          <p className="inst-hero-note">
            Chaque fiche énonce son éligibilité, son calendrier annoncé et
            le lien du site officiel. Aucune date n'est publiée à la place
            des administrations : leurs calendriers font foi. Les avis et
            communiqués en PDF sont joints par l'institution, puis
            téléchargeables tels quels.
          </p>
        </div>
        <div className="inst-hero-badge">
          <span className="inst-hero-badge-num">{sections.length}</span>
          <span className="inst-hero-badge-label">
            institution{plural(sections.length, "", "s")} publique{plural(sections.length, "", "s")}
          </span>
          <span className="inst-hero-badge-note">
            {items.length} programmes recensés
          </span>
        </div>
      </section>

      {/* ---------- Indicateurs réels ---------- */}
      <div className="opps-stats inst-stats">
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

      {/* ---------- Navigation par institution ---------- */}
      <nav className="inst-rail" aria-label="Institutions">
        <button
          type="button"
          className={`inst-stamp${active === "all" ? " is-active" : ""}`}
          onClick={() => openInstitution("all")}
        >
          <span className="inst-stamp-icon"><Icon d={I.layers} size={17} /></span>
          <span className="inst-stamp-text">
            <strong>Toutes</strong>
            <span>{items.length} programmes</span>
          </span>
        </button>
        {sections.map((s) => (
          <button
            key={s.category}
            type="button"
            className={`inst-stamp tone-${s.meta.tone}${active === s.category ? " is-active" : ""}`}
            onClick={() => openInstitution(s.category)}
            title={s.meta.title}
          >
            <span className="inst-stamp-icon"><Icon d={s.meta.icon} size={17} /></span>
            <span className="inst-stamp-text">
              <strong>{s.meta.short}</strong>
              <span>{s.count} programme{plural(s.count, "", "s")}</span>
            </span>
          </button>
        ))}
      </nav>

      <div className="inst-body" ref={contentRef}>
        <div className="inst-main">
          {/* ---------- Annuaire des institutions ---------- */}
          {!selected && (
            <>
              <div className="inst-section-title">
                <div>
                  <h2>Choisir une institution</h2>
                  <p className="small muted">
                    Sept familles de programmes publics. Ouvrez une institution
                    pour lire ses fiches, ses calendriers et télécharger ses
                    documents officiels.
                  </p>
                </div>
                <span className="inst-section-count">
                  {sections.length} institutions
                </span>
              </div>
              <div className="inst-directory">
                {sections.map((s) => (
                  <InstitutionCard
                    key={s.category}
                    section={s}
                    onOpen={openInstitution}
                  />
                ))}
              </div>
            </>
          )}

          {/* ---------- Fiches d'une institution ---------- */}
          {selected && (
            <section className={`inst-focus tone-${selected.meta.tone}`}>
              <header className="inst-focus-head">
                <span className="inst-focus-icon">
                  <Icon d={selected.meta.icon} size={22} />
                </span>
                <div className="inst-focus-copy">
                  <span className="inst-focus-eyebrow">Institution</span>
                  <h2>{selected.meta.title}</h2>
                  <p>{selected.meta.intro}</p>
                </div>
                <span className="inst-focus-count">
                  {selected.meta.key === "minesup" && minesup
                    ? `${minesup.length} université${plural(minesup.length, "", "s")}`
                    : `${selected.count} programme${plural(selected.count, "", "s")}`}
                </span>
              </header>
              <div className="inst-focus-body">
                {selected.meta.key === "minesup" ? (
                  <>
                    {minesup === null ? (
                      <Loader />
                    ) : minesup.length === 0 ? (
                      <Empty title="Catalogue MINESUP en préparation">
                        <p>
                          Les universités et leurs écoles seront publiées dès
                          leur enregistrement dans la console d'administration.
                        </p>
                      </Empty>
                    ) : (
                      <MinesupExplorer universities={minesup} />
                    )}
                    {selected.groups.length > 0 && (
                      <div className="minesup-notices">
                        <div className="minesup-notices-head">
                          <h3>Avis et procédures MINESUP</h3>
                          <p className="small muted">
                            Communiqués et échéances publiés par le ministère.
                          </p>
                        </div>
                        {selected.groups.map((g) => (
                          <InstitutionGroup key={g.key} group={g} />
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  selected.groups.map((g) => (
                    <InstitutionGroup key={g.key} group={g} />
                  ))
                )}
              </div>
            </section>
          )}

          {sections.length === 0 && (
            <Empty title="Aucun programme disponible">
              <p>
                Le référentiel public est vide : les programmes apparaîtront
                dès leur enregistrement par l'administration.
              </p>
            </Empty>
          )}

          <AssistantChat compact suggestions={PROGRAMS_SUGGESTIONS} pageContext="Programmes" />
        </div>

        {/* ---------- Colonne latérale ---------- */}
        <aside className="inst-side">
          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.clipboard} size={16} /> Lire une fiche</h2>
            </div>
            <ol className="learn-howto-steps">
              <li>
                <span className="learn-howto-num">1</span>
                <div>
                  <strong>Repérer le dispositif</strong>
                  <p>
                    Concours, emplois, stages, bourses ou appels à projets :
                    la sous-section dit de quoi il s'agit.
                  </p>
                </div>
              </li>
              <li>
                <span className="learn-howto-num">2</span>
                <div>
                  <strong>Vérifier l'éligibilité</strong>
                  <p>
                    Diplômes, âge, situation professionnelle : la fiche
                    reprend les conditions annoncées.
                  </p>
                </div>
              </li>
              <li>
                <span className="learn-howto-num">3</span>
                <div>
                  <strong>Télécharger les PDF</strong>
                  <p>
                    Avis et communiqués sont joints par l'institution ; le
                    site officiel reste la source qui fait foi.
                  </p>
                </div>
              </li>
            </ol>
          </section>

          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.link} size={16} /> Et ensuite ?</h2>
            </div>
            <ul className="learn-links">
              <li>
                <Link to="/learning">
                  <Icon d={I.book} size={15} /> Monter les compétences demandées
                </Link>
              </li>
              <li>
                <Link to="/opportunites">
                  <Icon d={I.briefcase} size={15} /> Postuler aux offres du marché
                </Link>
              </li>
              <li>
                <Link to="/entrepreneuriat">
                  <Icon d={I.rocket} size={15} /> Financer mon activité
                </Link>
              </li>
            </ul>
          </section>

          <p className="inst-side-note">
            Les institutions pourront tenir elles-mêmes leurs programmes et
            leurs PDF depuis un espace dédié : c'est l'ambition de la
            plateforme.
          </p>
        </aside>
      </div>
    </div>
  );
}
