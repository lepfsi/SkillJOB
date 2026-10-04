import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { CONTRACT_TYPES, fmtDate } from "../../lib.js";
import { Loader, ErrorNote } from "../../components/ui.jsx";

// Gestion de la base locale d'offres : création, édition, suppression.
// La traçabilité (source, URL, date) reste obligatoire (§51).

const EMPTY_FORM = {
  title: "",
  company: "",
  location: "",
  sector: "",
  contract_type: "CDI",
  description: "",
  requirements: "",
  salary: "",
  source_name: "Saisie manuelle",
  source_url: "",
  skills: [{ name: "", importance: "core" }],
};

function JobForm({ initial, onCancel, onSaved }) {
  const [form, setForm] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setSkill = (i, k, v) =>
    setForm((f) => ({
      ...f,
      skills: f.skills.map((s, j) => (j === i ? { ...s, [k]: v } : s)),
    }));

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = {
        title: form.title,
        company: form.company,
        location: form.location,
        sector: form.sector,
        contract_type: form.contract_type,
        description: form.description,
        requirements: form.requirements,
        salary: form.salary || null,
        source_name: form.source_name || "Saisie manuelle",
        source_url: form.source_url,
        required_skills: form.skills
          .filter((s) => s.name.trim())
          .map((s) => ({ name: s.name.trim(), importance: s.importance })),
      };
      if (form.id) {
        await api(`/admin/jobs/${form.id}`, { method: "PUT", body: payload });
      } else {
        await api("/admin/jobs", { method: "POST", body: payload });
      }
      onSaved();
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={submit}>
      <h2>{form.id ? "Modifier l'offre" : "Nouvelle offre"}</h2>
      <ErrorNote error={error} />
      <div className="grid-2">
        <label className="field">
          <span>Intitulé du poste *</span>
          <input value={form.title} onChange={(e) => set("title", e.target.value)} required />
        </label>
        <label className="field">
          <span>Entreprise *</span>
          <input value={form.company} onChange={(e) => set("company", e.target.value)} required />
        </label>
        <label className="field">
          <span>Localisation</span>
          <input value={form.location} onChange={(e) => set("location", e.target.value)} placeholder="Douala" />
        </label>
        <label className="field">
          <span>Secteur</span>
          <input value={form.sector} onChange={(e) => set("sector", e.target.value)} placeholder="Informatique / IT" />
        </label>
        <label className="field">
          <span>Type de contrat</span>
          <select value={form.contract_type} onChange={(e) => set("contract_type", e.target.value)}>
            {CONTRACT_TYPES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Salaire (si affiché)</span>
          <input value={form.salary || ""} onChange={(e) => set("salary", e.target.value)} placeholder="300 000 – 500 000 FCFA" />
        </label>
      </div>
      <label className="field">
        <span>Description</span>
        <textarea rows="3" value={form.description} onChange={(e) => set("description", e.target.value)} />
      </label>
      <label className="field">
        <span>Profil recherché</span>
        <textarea rows="2" value={form.requirements} onChange={(e) => set("requirements", e.target.value)} />
      </label>
      <label className="field">
        <span>Compétences requises (nom + importance)</span>
      </label>
      {form.skills.map((s, i) => (
        <div className="inline-fields" key={i}>
          <input
            style={{ flex: "1 1 220px" }}
            value={s.name}
            onChange={(e) => setSkill(i, "name", e.target.value)}
            placeholder="Ex. Excel avancé"
          />
          <select
            style={{ flex: "0 0 160px" }}
            value={s.importance}
            onChange={(e) => setSkill(i, "importance", e.target.value)}
          >
            <option value="core">Essentielle</option>
            <option value="preferred">Appréciée</option>
          </select>
          <button
            type="button"
            className="btn btn-ghost btn-small"
            onClick={() => setForm((f) => ({ ...f, skills: f.skills.filter((_, j) => j !== i) }))}
          >
            Retirer
          </button>
        </div>
      ))}
      <button
        type="button"
        className="btn btn-outline btn-small"
        onClick={() => setForm((f) => ({ ...f, skills: [...f.skills, { name: "", importance: "core" }] }))}
      >
        Ajouter une compétence
      </button>
      <div className="grid-2">
        <label className="field">
          <span>Nom de la source</span>
          <input value={form.source_name} onChange={(e) => set("source_name", e.target.value)} />
        </label>
        <label className="field">
          <span>URL de la source (traçabilité §51)</span>
          <input value={form.source_url} onChange={(e) => set("source_url", e.target.value)} placeholder="https://…" />
        </label>
      </div>
      <div className="actions-row">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Enregistrement…" : form.id ? "Mettre à jour" : "Publier l'offre"}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Annuler
        </button>
      </div>
    </form>
  );
}

function ParseHelper({ onParsed }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function parse(e) {
    e.preventDefault();
    if (text.trim().length < 10) {
      setError("Décrivez l'offre en une phrase au moins (10 caractères).");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const draft = await api("/jobs/parse", { method: "POST", body: { description: text } });
      onParsed(draft);
      setText("");
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={parse}>
      <h2>Générer depuis une description (assistant IA)</h2>
      <p className="small muted">
        L'assistant pré-remplit le formulaire depuis une brève description :
        vérifiez et complétez avant enregistrement.
      </p>
      {error && <ErrorNote error={error} />}
      <textarea
        rows="3"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Ex. Recrutement d'un infirmier diplômé d'État à l'hôpital régional de Bafoussam. Contrat : CDD 12 mois."
      />
      <div className="actions-row">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Analyse…" : "Pré-remplir le formulaire"}
        </button>
      </div>
    </form>
  );
}

export default function AdminJobs() {
  const [jobs, setJobs] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [importUrl, setImportUrl] = useState("");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState("");
  const [importNotice, setImportNotice] = useState("");

  async function importFromUrl(e) {
    e.preventDefault();
    setImporting(true);
    setImportError("");
    setImportNotice("");
    try {
      const draft = await api("/admin/import-url", { method: "POST", body: { url: importUrl } });
      setForm({
        title: draft.title || "",
        company: draft.company || "",
        location: draft.location || "",
        sector: draft.sector || "",
        contract_type: draft.contract_type || "CDI",
        description: draft.description || "",
        requirements: draft.requirements || "",
        salary: draft.salary || "",
        source_name: "Import URL",
        source_url: importUrl,
        skills: (draft.required_skills || []).length > 0
          ? draft.required_skills.map((s) => ({ name: s.name, importance: s.importance }))
          : [{ name: "", importance: "core" }],
      });
      setImportNotice("Brouillon extrait : vérifiez chaque champ avant d'enregistrer.");
      setImportUrl("");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setImportError(err.detail);
    } finally {
      setImporting(false);
    }
  }

  const reload = () => {
    setForm(null);
    api("/admin/jobs").then(setJobs).catch((e) => setError(e.detail));
  };

  useEffect(() => {
    reload();
  }, []);

  if (error && !jobs) return <div className="page"><ErrorNote error={error} /></div>;
  if (!jobs) return <div className="page"><Loader /></div>;

  async function remove(job) {
    if (!window.confirm(`Supprimer « ${job.title} » (${job.company}) ? Les candidatures liées seront également supprimées.`)) {
      return;
    }
    try {
      await api(`/admin/jobs/${job.id}`, { method: "DELETE" });
      reload();
    } catch (err) {
      setError(err.detail);
    }
  }

  function edit(job) {
    setForm({
      ...job,
      skills: (job.required_skills || []).length > 0
        ? job.required_skills.map((s) => ({ name: s.name, importance: s.importance }))
        : [{ name: "", importance: "core" }],
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function fromParsed(draft) {
    setForm({
      title: draft.title || "",
      company: draft.company || "",
      location: draft.location || "",
      sector: draft.sector || "",
      contract_type: draft.contract_type || "CDI",
      description: draft.description || "",
      requirements: draft.requirements || "",
      salary: draft.salary || "",
      source_name: "Saisie assistée",
      source_url: "",
      skills: (draft.required_skills || []).length > 0
        ? draft.required_skills.map((s) => ({ name: s.name, importance: s.importance }))
        : [{ name: "", importance: "core" }],
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="page">
      <h1>Base d'offres</h1>
      <p className="page-lead">
        {jobs.length} offre(s) en base. Chaque offre conserve sa source, son
        URL et sa date de publication (traçabilité §51).
      </p>
      <ErrorNote error={error} />
      <div className="actions-row">
        <button
          className="btn btn-primary"
          onClick={() => setForm({ ...EMPTY_FORM, skills: [{ name: "", importance: "core" }] })}
        >
          Nouvelle offre
        </button>
      </div>

      {!form && <ParseHelper onParsed={fromParsed} />}

      {!form && (
        <form className="panel" onSubmit={importFromUrl}>
          <h2>Importer depuis une URL (LinkedIn ou autre)</h2>
          <p className="small muted">
            Le système lit le balisage public de la page (JSON-LD) et
            pré-remplit le formulaire : vérifiez avant publication.
          </p>
          {importError && <ErrorNote error={importError} />}
          {importNotice && <div className="alert alert-success">{importNotice}</div>}
          <label className="field">
            <span>URL de l'offre</span>
            <input
              value={importUrl}
              onChange={(e) => setImportUrl(e.target.value)}
              placeholder="https://www.linkedin.com/jobs/view/…"
            />
          </label>
          <div className="actions-row">
            <button className="btn btn-primary" disabled={importing || !importUrl.trim()}>
              {importing ? "Analyse…" : "Extraire l'offre"}
            </button>
          </div>
        </form>
      )}

      {form && <JobForm initial={form} onCancel={() => setForm(null)} onSaved={reload} />}

      <div className="table-wrap" style={{ marginTop: "1rem" }}>
        <table className="skills">
          <thead>
            <tr>
              <th>Offre</th>
              <th>Localisation</th>
              <th>Contrat</th>
              <th>Publiée le</th>
              <th>Source</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id}>
                <td>
                  <strong>{j.title}</strong>
                  <div className="small muted">{j.company} · {j.sector}</div>
                </td>
                <td>{j.location}</td>
                <td>{j.contract_type}</td>
                <td>{fmtDate(j.published_at)}</td>
                <td className="small">
                  {j.source_name}
                  {j.source_url && (
                    <>
                      {" "}
                      <a href={j.source_url} target="_blank" rel="noreferrer">lien</a>
                    </>
                  )}
                </td>
                <td>
                  <div className="actions-row" style={{ marginTop: 0 }}>
                    <button className="btn btn-ghost btn-small" onClick={() => edit(j)}>
                      Modifier
                    </button>
                    <button className="btn btn-danger btn-small" onClick={() => remove(j)}>
                      Supprimer
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
