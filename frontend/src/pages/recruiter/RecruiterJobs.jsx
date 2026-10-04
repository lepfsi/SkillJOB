import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import { CONTRACT_TYPES, fmtDate } from "../../lib.js";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";

// Publication et gestion des offres de l'entreprise (branding automatique).
const EMPTY_FORM = {
  title: "",
  company: "",
  location: "",
  sector: "",
  contract_type: "CDI",
  description: "",
  requirements: "",
  salary: "",
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
        source_url: form.source_url,
        required_skills: form.skills
          .filter((s) => s.name.trim())
          .map((s) => ({ name: s.name.trim(), importance: s.importance })),
      };
      if (form.id) {
        await api(`/recruiter/jobs/${form.id}`, { method: "PUT", body: payload });
      } else {
        await api("/recruiter/jobs", { method: "POST", body: payload });
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
      <h2>{form.id ? "Modifier l'offre" : "Publier une offre"}</h2>
      <p className="small muted">
        Votre entreprise et son branding sont attachés automatiquement à
        l'offre (traçabilité §51 conservée).
      </p>
      <ErrorNote error={error} />
      <div className="grid-2">
        <label className="field">
          <span>Intitulé du poste *</span>
          <input value={form.title} onChange={(e) => set("title", e.target.value)} required />
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
          <input value={form.salary || ""} onChange={(e) => set("salary", e.target.value)} placeholder="300 000 FCFA et plus" />
        </label>
        <label className="field">
          <span>Lien externe (optionnel)</span>
          <input value={form.source_url || ""} onChange={(e) => set("source_url", e.target.value)} placeholder="https://…" />
        </label>
      </div>
      <label className="field">
        <span>Description du poste</span>
        <textarea rows="3" value={form.description} onChange={(e) => set("description", e.target.value)} />
      </label>
      <label className="field">
        <span>Profil recherché</span>
        <textarea rows="2" value={form.requirements} onChange={(e) => set("requirements", e.target.value)} />
      </label>
      <label className="field">
        <span>Compétences requises</span>
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
            className="btn btn-remove btn-small"
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
        Décrivez l'offre en une phrase : l'assistant pré-remplit le
        formulaire (poste, localisation, contrat, compétences reconnues).
        Vous vérifiez et complétez avant publication : rien n'est inventé.
      </p>
      {error && <ErrorNote error={error} />}
      <textarea
        rows="3"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Ex. Nous recrutons un technicien support informatique chez Numérik Services à Douala. CDI. Compétences : Windows Server, TCP/IP."
      />
      <div className="actions-row">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Analyse…" : "Pré-remplir le formulaire"}
        </button>
      </div>
    </form>
  );
}

export default function RecruiterJobs() {
  const [jobs, setJobs] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");

  const reload = () => {
    setForm(null);
    api("/recruiter/jobs").then(setJobs).catch((e) => setError(e.detail));
  };

  useEffect(() => {
    reload();
  }, []);

  if (error && !jobs) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!jobs) {
    return <div className="page"><Loader /></div>;
  }

  async function remove(job) {
    if (!window.confirm(`Supprimer « ${job.title} » ? Les candidatures liées seront supprimées.`)) {
      return;
    }
    try {
      await api(`/recruiter/jobs/${job.id}`, { method: "DELETE" });
      reload();
    } catch (err) {
      setError(err.detail);
    }
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
      source_url: "",
      skills: (draft.required_skills || []).length > 0
        ? draft.required_skills.map((s) => ({ name: s.name, importance: s.importance }))
        : [{ name: "", importance: "core" }],
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="page">
      <h1>Mes offres</h1>
      <p className="page-lead">{jobs.length} offre(s) publiée(s) par votre entreprise.</p>
      <ErrorNote error={error} />

      <div className="actions-row">
        <button
          className="btn btn-primary"
          onClick={() => setForm({ ...EMPTY_FORM, skills: [{ name: "", importance: "core" }] })}
        >
          Publier une offre
        </button>
      </div>

      {!form && <ParseHelper onParsed={fromParsed} />}

      {form && <JobForm initial={form} onCancel={() => setForm(null)} onSaved={reload} />}

      {jobs.length === 0 && !form && (
        <Empty title="Aucune offre publiée">
          <p>Publiez votre première offre : elle apparaîtra auprès des talents avec votre branding.</p>
        </Empty>
      )}

      {jobs.map((j) => (
        <div className="app-row" key={j.id}>
          <div className="app-head">
            <div>
              <strong>{j.title}</strong>
              <p className="job-meta" style={{ margin: "0.15rem 0" }}>
                {j.location} · {j.contract_type} · publiée le {fmtDate(j.published_at)}
              </p>
            </div>
            <div className="actions-row" style={{ marginTop: 0 }}>
              <button
                className="btn btn-ghost btn-small"
                onClick={() => setForm({
                  ...j,
                  skills: (j.required_skills || []).length > 0
                    ? j.required_skills.map((s) => ({ name: s.name, importance: s.importance }))
                    : [{ name: "", importance: "core" }],
                })}
              >
                Modifier
              </button>
              <button className="btn btn-remove btn-small" onClick={() => remove(j)}>
                Supprimer
              </button>
              <Link className="btn btn-ghost btn-small" to={`/opportunites/${j.id}`}>
                Aperçu
              </Link>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
