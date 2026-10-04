import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { INSTITUTION_LABELS, ENTREPRENEUR_KIND_LABELS } from "../../lib.js";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";

// Gestion des contenus publics : Programmes publics (FNE, MINFOP, MINPME,
// concours) et ressources Entrepreneuriat. CRUD complet côté admin.

const SUBCATEGORY_OPTIONS = [
  "", "fonction_publique", "grandes_ecoles", "sante", "forets_faune",
  "armees", "bourses", "offres_emploi", "accompagnement_pme",
];

const SUBCATEGORY_LABELS = {
  "": "Aucune",
  fonction_publique: "Fonction publique",
  grandes_ecoles: "Grandes écoles",
  sante: "Santé",
  forets_faune: "Forêts & faune",
  armees: "Armées & sécurité",
  bourses: "Bourses de formation",
  offres_emploi: "Offres d'emploi",
  accompagnement_pme: "Accompagnement PME",
};

function InstitutionalTab() {
  const [items, setItems] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");

  const reload = () => {
    setForm(null);
    api("/admin/public-content/institutional")
      .then(setItems)
      .catch((e) => setError(e.detail));
  };

  useEffect(() => { reload(); }, []);

  async function save(e) {
    e.preventDefault();
    try {
      const body = { ...form, subcategory: form.subcategory || null };
      if (form.id) {
        await api(`/admin/public-content/institutional/${form.id}`, { method: "PUT", body });
      } else {
        await api("/admin/public-content/institutional", { method: "POST", body });
      }
      reload();
    } catch (err) {
      setError(err.detail);
    }
  }

  async function remove(item) {
    if (!window.confirm(`Supprimer « ${item.title} » ?`)) return;
    try {
      await api(`/admin/public-content/institutional/${item.id}`, { method: "DELETE" });
      reload();
    } catch (err) {
      setError(err.detail);
    }
  }

  if (!items) return <Loader />;

  return (
    <div>
      <div className="actions-row">
        <button className="btn btn-primary" onClick={() => setForm({
          category: "concours", subcategory: "", title: "",
          description: "", eligibility: "", url: "", deadline: "",
        })}>
          Nouveau programme public
        </button>
      </div>
      {form && (
        <form className="panel" onSubmit={save}>
          <h2>{form.id ? "Modifier le programme" : "Nouveau programme public"}</h2>
          <div className="grid-2">
            <label className="field">
              <span>Institution *</span>
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                {Object.entries(INSTITUTION_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label className="field">
              <span>Sous-catégorie (concours, bourses…)</span>
              <select value={form.subcategory} onChange={(e) => setForm({ ...form, subcategory: e.target.value })}>
                {SUBCATEGORY_OPTIONS.map((s) => <option key={s} value={s}>{SUBCATEGORY_LABELS[s]}</option>)}
              </select>
            </label>
          </div>
          <label className="field">
            <span>Titre *</span>
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea rows="2" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </label>
          <div className="grid-2">
            <label className="field">
              <span>Éligibilité</span>
              <input value={form.eligibility} onChange={(e) => setForm({ ...form, eligibility: e.target.value })} />
            </label>
            <label className="field">
              <span>Calendrier</span>
              <input value={form.deadline} onChange={(e) => setForm({ ...form, deadline: e.target.value })} placeholder="Ex. Sessions annuelles" />
            </label>
          </div>
          <label className="field">
            <span>Lien officiel</span>
            <input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://…" />
          </label>
          <div className="actions-row">
            <button className="btn btn-primary">Enregistrer</button>
            <button type="button" className="btn btn-ghost" onClick={() => setForm(null)}>Annuler</button>
          </div>
        </form>
      )}
      {items.length === 0 && <Empty title="Aucun programme" />}
      {items.map((item) => (
        <div className="app-row" key={item.id}>
          <div className="app-head">
            <div>
              <strong>{item.title}</strong>
              <p className="job-meta" style={{ margin: "0.15rem 0" }}>
                {INSTITUTION_LABELS[item.category] || item.category}
                {item.subcategory && ` · ${SUBCATEGORY_LABELS[item.subcategory] || item.subcategory}`}
              </p>
            </div>
            <div className="actions-row" style={{ marginTop: 0 }}>
              <button className="btn btn-ghost btn-small" onClick={() => setForm({ ...item })}>Modifier</button>
              <button className="btn btn-remove btn-small" onClick={() => remove(item)}>Supprimer</button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function EntrepreneurTab() {
  const [items, setItems] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");

  const reload = () => {
    setForm(null);
    api("/admin/public-content/entrepreneurship")
      .then(setItems)
      .catch((e) => setError(e.detail));
  };

  useEffect(() => { reload(); }, []);

  async function save(e) {
    e.preventDefault();
    try {
      const body = {
        ...form,
        sectors: (form.sectors_str || "").split(",").map((s) => s.trim()).filter(Boolean),
      };
      delete body.sectors_str;
      if (form.id) {
        await api(`/admin/public-content/entrepreneurship/${form.id}`, { method: "PUT", body });
      } else {
        await api("/admin/public-content/entrepreneurship", { method: "POST", body });
      }
      reload();
    } catch (err) {
      setError(err.detail);
    }
  }

  async function remove(item) {
    if (!window.confirm(`Supprimer « ${item.title} » ?`)) return;
    try {
      await api(`/admin/public-content/entrepreneurship/${item.id}`, { method: "DELETE" });
      reload();
    } catch (err) {
      setError(err.detail);
    }
  }

  if (!items) return <Loader />;

  return (
    <div>
      <div className="actions-row">
        <button className="btn btn-primary" onClick={() => setForm({
          kind: "concours", title: "", description: "",
          organizer: "", url: "", sectors_str: "",
        })}>
          Nouvelle ressource entrepreneuriat
        </button>
      </div>
      {form && (
        <form className="panel" onSubmit={save}>
          <h2>{form.id ? "Modifier la ressource" : "Nouvelle ressource"}</h2>
          <div className="grid-2">
            <label className="field">
              <span>Type *</span>
              <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
                {Object.entries(ENTREPRENEUR_KIND_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label className="field">
              <span>Organisateur</span>
              <input value={form.organizer} onChange={(e) => setForm({ ...form, organizer: e.target.value })} />
            </label>
          </div>
          <label className="field">
            <span>Titre *</span>
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea rows="2" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </label>
          <div className="grid-2">
            <label className="field">
              <span>Lien</span>
              <input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://…" />
            </label>
            <label className="field">
              <span>Secteurs (séparés par des virgules)</span>
              <input
                value={form.sectors_str ?? (form.sectors || []).join(", ")}
                onChange={(e) => setForm({ ...form, sectors_str: e.target.value })}
                placeholder="Ex. Numérique, Agriculture"
              />
            </label>
          </div>
          <div className="actions-row">
            <button className="btn btn-primary">Enregistrer</button>
            <button type="button" className="btn btn-ghost" onClick={() => setForm(null)}>Annuler</button>
          </div>
        </form>
      )}
      {items.length === 0 && <Empty title="Aucune ressource" />}
      {items.map((item) => (
        <div className="app-row" key={item.id}>
          <div className="app-head">
            <div>
              <strong>{item.title}</strong>
              <p className="job-meta" style={{ margin: "0.15rem 0" }}>
                {ENTREPRENEUR_KIND_LABELS[item.kind] || item.kind}
                {item.organizer ? ` · ${item.organizer}` : ""}
              </p>
            </div>
            <div className="actions-row" style={{ marginTop: 0 }}>
              <button className="btn btn-ghost btn-small" onClick={() => setForm({ ...item, sectors_str: (item.sectors || []).join(", ") })}>Modifier</button>
              <button className="btn btn-remove btn-small" onClick={() => remove(item)}>Supprimer</button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function AdminPublicContent() {
  const [tab, setTab] = useState("institutional");

  return (
    <div className="page">
      <h1>Programmes publics & entrepreneuriat</h1>
      <p className="page-lead">
        Gestion des contenus affichés aux jeunes : concours, bourses,
        accompagnements ministériels et ressources entrepreneuriat.
      </p>
      <ErrorNote error={null} />
      <div className="doc-filters" style={{ marginTop: "1rem" }}>
        <button
          type="button"
          className={`doc-filter ${tab === "institutional" ? "active" : ""}`}
          onClick={() => setTab("institutional")}
        >
          Programmes publics
        </button>
        <button
          type="button"
          className={`doc-filter ${tab === "entrepreneurship" ? "active" : ""}`}
          onClick={() => setTab("entrepreneurship")}
        >
          Entrepreneuriat
        </button>
      </div>
      {tab === "institutional" ? <InstitutionalTab /> : <EntrepreneurTab />}
    </div>
  );
}
