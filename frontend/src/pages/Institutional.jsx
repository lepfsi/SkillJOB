import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";

// Programmes publics camerounais, restructurés : concours (fonction
// publique, grandes écoles, ministères techniques), FNE, MINFOP, MINPME.

const SECTIONS = [
  {
    category: "concours",
    title: "Concours et examens",
    intro: "Fonction publique, grandes écoles et ministères techniques.",
  },
  {
    category: "fne",
    title: "Offres d'emploi : Fonds National de l'Emploi",
    intro: "Emplois, stages et contrats préprofessionnels publiés en continu.",
  },
  {
    category: "minfop",
    title: "Bourses de formation : MINFOP",
    intro: "Formations professionnelles financées et reconnaissance des compétences de terrain.",
  },
  {
    category: "minpme",
    title: "PME et entrepreneuriat : MINPME",
    intro: "Accompagnement et financement des très petites entreprises.",
  },
];

export default function Institutional() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const [active, setActive] = useState("all");

  useEffect(() => {
    api("/institutional").then(setItems).catch((e) => setError(e.detail));
  }, []);

  if (error && !items) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!items) {
    return <div className="page"><Loader /></div>;
  }

  const sections = SECTIONS.map((s) => ({
    ...s,
    items: items.filter((i) => i.category === s.category),
  })).filter((s) => s.items.length > 0);

  const renderable = active === "all" ? sections : sections.filter((s) => s.category === active);

  return (
    <div className="page">
      <h1>Programmes publics</h1>
      <p className="page-lead">
        Concours, bourses, offres d'emploi et accompagnements des
        administrations camerounaises, organisés par institution.
      </p>

      <div className="doc-filters" style={{ marginTop: "1rem" }}>
        <button
          type="button"
          className={`doc-filter ${active === "all" ? "active" : ""}`}
          onClick={() => setActive("all")}
        >
          Tout ({items.length})
        </button>
        {sections.map((s) => (
          <button
            key={s.category}
            type="button"
            className={`doc-filter ${active === s.category ? "active" : ""}`}
            onClick={() => setActive(s.category)}
          >
            {s.title} ({s.items.length})
          </button>
        ))}
      </div>

      {renderable.map((section) => (
        <section className="section" key={section.category}>
          <div className="section-head">
            <h2>{section.title}</h2>
            <span className="small muted">{section.intro}</span>
          </div>
          {section.items.map((item) => (
            <div className="panel" key={item.id}>
              <div className="section-head">
                <h3 style={{ margin: 0 }}>{item.title}</h3>
                {item.subcategory_label && (
                  <span className="badge badge-strong">{item.subcategory_label}</span>
                )}
              </div>
              <p className="small">{item.description}</p>
              {item.eligibility && (
                <p className="small muted">Éligibilité : {item.eligibility}</p>
              )}
              <div className="actions-row" style={{ marginTop: "0.4rem" }}>
                {item.url && (
                  <a className="btn btn-outline btn-small" href={item.url} target="_blank" rel="noreferrer">
                    Site officiel
                  </a>
                )}
                {item.deadline && (
                  <span className="small muted">Calendrier : {item.deadline}</span>
                )}
              </div>
            </div>
          ))}
        </section>
      ))}

      {sections.length === 0 && <Empty title="Aucun programme disponible" />}
    </div>
  );
}
