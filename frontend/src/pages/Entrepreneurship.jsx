import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { ENTREPRENEUR_KIND_LABELS } from "../lib.js";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";

// Espace entrepreneuriat interactif (§11bis) : guidance personnalisée,
// génération de business plan, institutions de financement, préparation
// bancaire. Des informations concrètes, jamais de promesses.

const KINDS = ["concours", "accompagnement", "financement", "formation"];

function GuidanceBlock() {
  const [guidance, setGuidance] = useState(null);

  useEffect(() => {
    api("/entrepreneurship/guidance").then(setGuidance).catch(() => setGuidance(null));
  }, []);

  if (!guidance) return null;
  return (
    <section className="panel">
      <div className="section-head">
        <h2>Comment entreprendre dans MON domaine</h2>
        {guidance.category_label && (
          <span className="badge badge-strong">{guidance.category_label}</span>
        )}
      </div>
      <p>{guidance.introduction}</p>
      {guidance.opportunities.length > 0 && (
        <>
          <h3>Pistes concrètes dans votre domaine</h3>
          <ul className="explain-list">
            {guidance.opportunities.map((o, i) => <li key={i}>{o}</li>)}
          </ul>
        </>
      )}
      {guidance.steps.length > 0 && (
        <>
          <h3>Vos premières étapes</h3>
          <ul className="explain-list">
            {guidance.steps.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </>
      )}
    </section>
  );
}

function BusinessPlanBlock() {
  const [form, setForm] = useState({ activity: "", target: "", capital: "", location: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const doc = await api("/entrepreneurship/business-plan", { method: "POST", body: form });
      setDone(doc.id);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={submit}>
      <h2>Construire mon business plan</h2>
      <p className="small muted">
        L'assistant structure un business plan à partir de VOS informations
        et des compétences de votre profil validé : rien n'est inventé. Le
        document est exportable et modifiable, à compléter avec votre étude
        de marché terrain.
      </p>
      <ErrorNote error={error} />
      {done && (
        <div className="alert alert-success">
          Business plan généré.{" "}
          <Link to={`/documents?open=${done}`}>Ouvrir dans mes documents →</Link>
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
          {busy ? "Génération…" : "Générer mon business plan"}
        </button>
      </div>
    </form>
  );
}

export default function Entrepreneurship() {
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");

  useEffect(() => {
    api("/entrepreneurship").then(setData).catch((e) => setError(e.detail));
  }, []);

  if (error && !data) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!data) {
    return <div className="page"><Loader /></div>;
  }

  const filtered = filter === "all"
    ? data.resources
    : data.resources.filter((r) => r.kind === filter);

  return (
    <div className="page">
      <h1>Entrepreneuriat</h1>
      <p className="page-lead">
        L'entrepreneuriat est une trajectoire professionnelle possible :
        l'assistant vous guide dans VOTRE domaine, construit votre business
        plan et référence les institutions de financement camerounaises.
      </p>

      <GuidanceBlock />
      <BusinessPlanBlock />

      <section className="panel">
        <h2>Financements publics et parapublics</h2>
        <p className="small muted">
          Institutions répertoriées pour accompagner ou octroyer des prêts aux
          entrepreneurs. Conditions indicatives : vérifiez toujours auprès de
          l'institution.
        </p>
        {data.financing_institutions.map((inst) => (
          <div className="panel-light" key={inst.name}>
            <div className="section-head">
              <h3 style={{ margin: 0 }}>{inst.name}</h3>
              <span className="badge badge-none">{inst.type}</span>
            </div>
            <p className="small">{inst.finances}</p>
            <p className="small muted">Conditions : {inst.conditions}</p>
            {inst.url && (
              <a className="small" href={inst.url} target="_blank" rel="noreferrer">
                Site officiel →
              </a>
            )}
          </div>
        ))}
      </section>

      <section className="panel">
        <h2>Ressources : concours, accompagnements, formations</h2>
        <div className="doc-filters">
          <button
            type="button"
            className={`doc-filter ${filter === "all" ? "active" : ""}`}
            onClick={() => setFilter("all")}
          >
            Tous ({data.resources.length})
          </button>
          {KINDS.map((k) => (
            <button
              key={k}
              type="button"
              className={`doc-filter ${filter === k ? "active" : ""}`}
              onClick={() => setFilter(k)}
            >
              {ENTREPRENEUR_KIND_LABELS[k]}
            </button>
          ))}
        </div>
        {filtered.length === 0 && <Empty title="Aucune ressource dans cette catégorie" />}
        {filtered.map((r) => (
          <div className="panel-light" key={r.id}>
            <div className="section-head">
              <h3 style={{ margin: 0 }}>{r.title}</h3>
              <span className="badge badge-strong">{r.kind_label}</span>
            </div>
            <p className="small">{r.description}</p>
            <p className="small muted">
              {r.organizer}
              {r.sectors && r.sectors.length > 0 && ` · ${r.sectors.join(" · ")}`}
            </p>
            {r.url && (
              <a className="small" href={r.url} target="_blank" rel="noreferrer">
                En savoir plus →
              </a>
            )}
          </div>
        ))}
      </section>

      <section className="panel">
        <h2>Préparer son dossier bancaire</h2>
        <p className="small muted">
          Répertoire des exigences généralement demandées par les banques et
          microfinances au Cameroun. Aucune obtention de crédit n'est garantie :
          c'est la banque qui décide.
        </p>
        {data.bank_prep.map((b) => (
          <div className="panel-light" key={b.step}>
            <h3>{b.step}</h3>
            <p className="small">{b.detail}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
