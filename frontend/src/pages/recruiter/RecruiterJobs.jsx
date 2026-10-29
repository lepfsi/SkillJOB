import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import { CONTRACT_TYPES, fmtDate } from "../../lib.js";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";
import { DomainPicker } from "../../components/DomainPicker.jsx";
import JobPublicView from "../../components/JobPublicView.jsx";

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

function JobWritingAssistant({ onApply }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [proposal, setProposal] = useState(null);
  const [applied, setApplied] = useState(false);

  async function generate() {
    if (text.trim().length < 10) {
      setError("Décrivez l'offre en une phrase au moins (10 caractères).");
      return;
    }
    setBusy(true);
    setError("");
    setApplied(false);
    try {
      const draft = await api("/jobs/write", {
        method: "POST",
        body: { description: text.trim() },
      });
      setProposal(draft);
    } catch (err) {
      setError(err.detail || "Proposition impossible");
    } finally {
      setBusy(false);
    }
  }

  function apply() {
    onApply(proposal);
    setProposal(null);
    setApplied(true);
  }

  function ignore() {
    setProposal(null);
    setApplied(false);
  }

  return (
    <div className={`job-writer${open ? " is-open" : ""}`}>
      <div className="job-writer-head">
        <div>
          <h3>Rédaction assistée</h3>
          <p className="small muted">
            Décrivez votre besoin en quelques phrases : l'assistant propose
            un intitulé, une description et un profil recherché. Rien n'est
            appliqué ni publié sans votre validation.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-outline btn-small"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Masquer" : "Ouvrir l'assistant"}
        </button>
      </div>
      {open && (
        <div className="job-writer-form">
          <label className="field">
            <span>Décrivez le poste et le besoin</span>
            <textarea
              rows="4"
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={4000}
              placeholder="Ex. Nous recherchons un technicien support informatique à Douala pour accompagner nos équipes. CDI. Windows Server, TCP/IP et sens du service."
            />
          </label>
          <div className="actions-row">
            <button
              type="button"
              className="btn btn-primary btn-small"
              disabled={busy || text.trim().length < 10}
              onClick={generate}
            >
              {busy ? "Rédaction…" : "Proposer une rédaction"}
            </button>
            <span className="small muted">
              La proposition reste un brouillon : relisez chaque champ.
            </span>
          </div>
          <ErrorNote error={error} />
          {applied && (
            <div className="alert alert-success">
              Suggestions appliquées au formulaire. Corrigez librement avant
              de publier.
            </div>
          )}
          {proposal && (
            <div className="job-writer-proposal">
              <div className="job-writer-proposal-head">
                <h4>Proposition à relire</h4>
                <span className="chip">
                  {proposal.mode === "llm" ? "Modèle IA" : "Règles locales"}
                </span>
              </div>
              <p className="small muted">{proposal.warning}</p>
              <dl className="job-writer-fields">
                <div>
                  <dt>Intitulé</dt>
                  <dd>{proposal.title || "À compléter"}</dd>
                </div>
                <div>
                  <dt>Lieu et contrat</dt>
                  <dd>
                    {[proposal.location, proposal.contract_type]
                      .filter(Boolean)
                      .join(" · ") || "À compléter"}
                  </dd>
                </div>
                <div>
                  <dt>Description</dt>
                  <dd className="job-writer-text">{proposal.description}</dd>
                </div>
                <div>
                  <dt>Profil recherché</dt>
                  <dd className="job-writer-text">{proposal.requirements}</dd>
                </div>
              </dl>
              {proposal.required_skills?.length > 0 && (
                <div className="chip-row">
                  {proposal.required_skills.map((skill) => (
                    <span className="chip" key={skill.name}>
                      {skill.name}
                      {skill.importance === "core" ? " · essentielle" : ""}
                    </span>
                  ))}
                </div>
              )}
              <div className="actions-row">
                <button
                  type="button"
                  className="btn btn-primary btn-small"
                  onClick={apply}
                >
                  Appliquer les suggestions
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-small"
                  onClick={ignore}
                >
                  Ignorer
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function JobForm({ initial, company, onCancel, onSaved, onPreview }) {
  const [form, setForm] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [previewSeen, setPreviewSeen] = useState(Boolean(initial.id));
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

  function applyProposal(draft) {
    setForm((f) => ({
      ...f,
      title: draft.title || f.title,
      location: draft.location || f.location,
      sector: draft.sector || f.sector,
      contract_type: draft.contract_type || f.contract_type,
      description: draft.description || f.description,
      requirements: draft.requirements || f.requirements,
      skills: draft.required_skills?.length
        ? draft.required_skills.map((skill) => ({
            name: skill.name,
            importance: skill.importance || "core",
          }))
        : f.skills,
    }));
    // Une proposition appliquée après un premier aperçu doit être relue
    // dans la fiche publique avant publication.
    setPreviewSeen(false);
  }

  function openPreview() {
    const skills = form.skills
      .filter((skill) => skill.name.trim())
      .map((skill) => ({
        name: skill.name.trim(),
        importance: skill.importance,
      }));
    onPreview({
      ...form,
      company: company?.name || form.company,
      company_branding: company
        ? {
            name: company.name,
            sector: company.sector,
            description: company.description,
            logo_url: company.logo_url,
          }
        : null,
      required_skills: skills,
      photo_url: photoPreview,
      email_reference: form.email_reference || "",
      source: {
        name: form.source_url ? "Lien externe" : "Espace recruteur",
        url: form.source_url || "",
      },
      apply_channel: form.apply_channel || "platform",
      deadline: form.deadline
        ? `${String(form.deadline).slice(0, 10)}T23:59:00`
        : null,
    });
    setPreviewSeen(true);
  }

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
      <div className="job-form-head">
        <h2>{form.id ? "Modifier l'offre" : "Publier une offre"}</h2>
        {!form.id && <span className="chip">Brouillon non publié</span>}
      </div>
      <p className="small muted">
        Votre entreprise et son branding sont attachés automatiquement à
        l'offre (traçabilité §51 conservée). Tant que vous n'avez pas cliqué
        sur « Publier l'offre », rien n'est enregistré.
      </p>
      <ErrorNote error={error} />
      <JobWritingAssistant onApply={applyProposal} />
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
        <button
          className="btn btn-primary"
          disabled={busy || (!form.id && !previewSeen)}
        >
          {busy ? "Enregistrement…" : form.id ? "Mettre à jour" : "Publier l'offre"}
        </button>
        <button type="button" className="btn btn-outline" onClick={openPreview}>
          Aperçu de la fiche publique
        </button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Annuler
        </button>
      </div>
      {!form.id && !previewSeen && (
        <p className="small muted">
          Ouvrez l'aperçu de la fiche publique avant de publier : vous
          vérifiez ainsi le rendu final, le branding et la référence.
        </p>
      )}
    </form>
  );
}

export default function RecruiterJobs() {
  const [jobs, setJobs] = useState(null);
  const [applications, setApplications] = useState(null);
  const [company, setCompany] = useState(null);
  const [form, setForm] = useState(null);
  const [previewJob, setPreviewJob] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const [error, setError] = useState("");

  const reload = () => {
    setForm(null);
    Promise.all([
      api("/recruiter/jobs"),
      api("/recruiter/applications").catch(() => []),
      api("/recruiter/company").catch(() => null),
    ])
      .then(([jobRows, applicationRows, companyRow]) => {
        setJobs(jobRows);
        setApplications(applicationRows);
        setCompany(companyRow);
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

  function previewExisting(job) {
    setPreviewJob({
      ...job,
      company: company?.name || job.company,
      company_branding: company
        ? {
            name: company.name,
            sector: company.sector,
            description: company.description,
            logo_url: company.logo_url,
          }
        : null,
      source: { name: job.source_name, url: job.source_url },
    });
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

      {form && (
        <JobForm
          initial={form}
          company={company}
          onCancel={() => setForm(null)}
          onSaved={reload}
          onPreview={setPreviewJob}
        />
      )}

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
              <button
                className="btn btn-ghost btn-small"
                onClick={() => previewExisting(j)}
              >
                Aperçu
              </button>
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

      {previewJob && (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => setPreviewJob(null)}
        >
          <div
            className="modal modal-wide job-preview-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="job-preview-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-head job-preview-head">
              <div>
                <h2 id="job-preview-title">Aperçu de la fiche publique</h2>
                <p className="small muted">
                  Rendu final tel que les candidats le verront. Le formulaire
                  de candidature n'est pas inclus dans cet aperçu.
                </p>
              </div>
              <button
                type="button"
                className="btn btn-ghost btn-small"
                onClick={() => setPreviewJob(null)}
              >
                Fermer
              </button>
            </div>
            <div className="job-preview-body">
              <JobPublicView job={previewJob} preview titleTag="h2" />
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setPreviewJob(null)}
              >
                Retour à la rédaction
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
