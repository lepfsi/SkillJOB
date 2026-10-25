import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import { CONTRACT_TYPES, fmtDate } from "../../lib.js";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";
import { DomainPicker } from "../../components/DomainPicker.jsx";

// Publication et gestion des offres de l'entreprise (branding automatique).
const EMPTY_FORM = {
  title: "",
  company: "",
  location: "",
  sector: "",
  domain_id: null,
  specialty_id: null,
  contract_type: "CDI",
  description: "",
  requirements: "",
  salary: "",
  deadline: "",
  source_url: "",
  apply_email: "",
  apply_keywords: [],
  skills: [{ name: "", importance: "core" }],
};

function JobForm({ initial, onCancel, onSaved }) {
  const [form, setForm] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [keywordsText, setKeywordsText] = useState(
    (initial.apply_keywords || []).join(", ")
  );
  // Photo FACULTATIVE de l'offre : envoyée après la publication (l'id de
  // l'offre est alors connu), comme côté administration.
  const [photoFile, setPhotoFile] = useState(null);
  const [removePhoto, setRemovePhoto] = useState(false);
  const [photoPreview, setPhotoPreview] = useState(initial.photo_url || "");

  useEffect(() => {
    if (!photoFile) {
      setPhotoPreview(removePhoto ? "" : (initial.photo_url || ""));
      return undefined;
    }
    const url = URL.createObjectURL(photoFile);
    setPhotoPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photoFile, removePhoto, initial.photo_url]);

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
        location: form.location,
        sector: form.sector,
        domain_id: form.domain_id || null,
        specialty_id: form.specialty_id || null,
        contract_type: form.contract_type,
        description: form.description,
        requirements: form.requirements,
        salary: form.salary || null,
        deadline: form.deadline
          ? `${String(form.deadline).slice(0, 10)}T23:59:00`
          : null,
        source_url: form.source_url,
        apply_email: (form.apply_email || "").trim() || null,
        apply_keywords: keywordsText
          .split(",")
          .map((word) => word.trim())
          .filter(Boolean),
        required_skills: form.skills
          .filter((s) => s.name.trim())
          .map((s) => ({ name: s.name.trim(), importance: s.importance })),
      };
      let saved;
      if (form.id) {
        saved = await api(`/recruiter/jobs/${form.id}`, { method: "PUT", body: payload });
      } else {
        saved = await api("/recruiter/jobs", { method: "POST", body: payload });
      }
      const jobId = saved?.id || form.id;
      if (jobId && photoFile) {
        const fd = new FormData();
        fd.append("file", photoFile);
        await api(`/recruiter/jobs/${jobId}/photo`, { method: "POST", form: fd });
      } else if (jobId && removePhoto) {
        await api(`/recruiter/jobs/${jobId}/photo`, { method: "DELETE" });
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
        <label className="field">
          <span>Date limite de candidature (facultatif)</span>
          <input
            type="date"
            value={form.deadline ? String(form.deadline).slice(0, 10) : ""}
            onChange={(e) => set("deadline", e.target.value)}
          />
        </label>
      </div>
      <DomainPicker
        domainId={form.domain_id}
        specialtyIds={form.specialty_id ? [form.specialty_id] : []}
        multiple={false}
        domainLabel="Domaine du poste"
        specialtyLabel="Spécialité recherchée"
        onChange={({ domain_id, specialty_ids }) =>
          setForm((f) => ({
            ...f,
            domain_id,
            specialty_id: specialty_ids?.[0] ?? null,
          }))
        }
        hint="Les talents peuvent ainsi vous retrouver par domaine et spécialité."
      />
      <label className="field">
        <span>Description du poste</span>
        <textarea rows="3" value={form.description} onChange={(e) => set("description", e.target.value)} />
      </label>
      <label className="field">
        <span>Profil recherché</span>
        <textarea rows="2" value={form.requirements} onChange={(e) => set("requirements", e.target.value)} />
      </label>

      <div className="job-route-box">
        <h3>Candidatures par e-mail</h3>
        <p>
          Le visuel public de l'offre indique au candidat d'envoyer son CV et
          sa lettre à l'adresse interne d'OrientSkill AI, avec la référence
          de l'offre. La candidature vous est ensuite transmise avec les
          pièces jointes d'origine.
        </p>
        <div className="job-route-grid">
          <label className="field">
            <span>Adresse de réception (RH)</span>
            <input
              type="email"
              value={form.apply_email || ""}
              onChange={(e) => set("apply_email", e.target.value)}
              placeholder="recrutement@entreprise.cm"
            />
            <span className="field-hint">
              Laissez vide pour recevoir sur l'e-mail de votre compte.
            </span>
          </label>
          <label className="field">
            <span>Mots-clés de routage</span>
            <input
              value={keywordsText}
              onChange={(e) => setKeywordsText(e.target.value)}
              placeholder="développeur, laravel, douala"
            />
            <span className="field-hint">
              Séparés par des virgules. Utiles si l'objet ne cite pas la référence.
            </span>
          </label>
        </div>
        <p className="small muted">
          Référence publique :{" "}
          <span className="job-reference">
            {form.email_reference || "attribuée après publication"}
          </span>
        </p>
      </div>

      {/* Photo FACULTATIVE : illustre l'offre côté talents. */}
      <div className="field">
        <span>Photo de l'offre (facultatif)</span>
        <div className="job-photo-field">
          <div className="job-photo-preview">
            {photoPreview
              ? <img src={photoPreview} alt="Aperçu de la photo de l'offre" />
              : <span>Aucune photo</span>}
          </div>
          <div className="job-photo-copy">
            <strong>Illustration visible par les candidats</strong>
            <p>
              JPG, PNG ou WebP, 5 Mo maximum. Facultative : une offre sans
              photo s'affiche normalement. Elle apparaît sur la carte et le
              détail de l'offre.
            </p>
            <div className="job-photo-actions">
              <label className="btn btn-outline btn-small">
                {photoFile ? "Changer la photo" : "Choisir une photo"}
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  hidden
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      setPhotoFile(file);
                      setRemovePhoto(false);
                    }
                  }}
                />
              </label>
              {(photoPreview || photoFile) && (
                <button
                  type="button"
                  className="btn btn-ghost btn-small"
                  onClick={() => { setPhotoFile(null); setRemovePhoto(true); }}
                >
                  Retirer
                </button>
              )}
              {photoFile && <span className="small muted">{photoFile.name}</span>}
            </div>
            <p>
              La photo est envoyée {form.id ? "après l'enregistrement" : "après la publication"}.
            </p>
          </div>
        </div>
      </div>
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
  const [applications, setApplications] = useState(null);
  const [form, setForm] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const [error, setError] = useState("");

  const reload = () => {
    setForm(null);
    Promise.all([
      api("/recruiter/jobs"),
      api("/recruiter/applications").catch(() => []),
    ])
      .then(([jobRows, applicationRows]) => {
        setJobs(jobRows);
        setApplications(applicationRows);
      })
      .catch((e) => setError(e.detail));
  };

  useEffect(() => {
    reload();
  }, []);

  if (error && !jobs) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!jobs || !applications) {
    return <div className="page"><Loader /></div>;
  }

  const applicationCounts = applications.reduce((acc, app) => {
    acc[app.job_id] = (acc[app.job_id] || 0) + 1;
    return acc;
  }, {});

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

  async function copyPublicLink(job) {
    const url = `${window.location.origin}/postuler/${job.id}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopiedId(job.id);
      window.setTimeout(() => setCopiedId(null), 3000);
    } catch {
      window.prompt("Copiez ce lien public de candidature :", url);
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
      deadline: String(draft.deadline || "").slice(0, 10),
      source_url: draft.source_url || "",
      apply_email: "",
      apply_keywords: [],
      email_reference: "",
      skills: (draft.required_skills || []).length > 0
        ? draft.required_skills.map((s) => ({ name: s.name, importance: s.importance }))
        : [{ name: "", importance: "core" }],
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="page">
      <h1>Mes offres</h1>
      <p className="page-lead">
        {jobs.length} offre(s) publiée(s) par votre entreprise, {applications.length} candidature(s) reçue(s).
        Le bouton « Lien public » copie une adresse de candidature rapide : un candidat non inscrit
        saisit nom, e-mail et téléphone, son compte est créé et sa candidature enregistrée.
      </p>
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
                {j.deadline ? ` · échéance : ${fmtDate(j.deadline)}` : ""}
                {` · ${applicationCounts[j.id] || 0} candidature(s)`}
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
              <button
                className="btn btn-outline btn-small"
                onClick={() => copyPublicLink(j)}
                title="Copier le lien public de candidature à partager"
              >
                {copiedId === j.id ? "Lien copié" : "Lien public"}
              </button>
              <Link
                className="btn btn-outline btn-small"
                to={`/visuel/${j.id}`}
                title="Visuel de candidature pour LinkedIn"
              >
                Visuel
              </Link>
              {(applicationCounts[j.id] || 0) > 0 && (
                <Link
                  className="btn btn-outline btn-small"
                  to={`/recruteur?offre=${j.id}#candidatures`}
                >
                  Candidatures ({applicationCounts[j.id]})
                </Link>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
