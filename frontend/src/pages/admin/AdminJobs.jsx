import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../../api/client.js";
import { CONTRACT_TYPES, fmtDate } from "../../lib.js";
import { Loader, ErrorNote } from "../../components/ui.jsx";
import { DomainPicker } from "../../components/DomainPicker.jsx";

// Gestion de la base locale d'offres : création, édition, suppression.
// La traçabilité (source, URL, date) reste obligatoire (§51).

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
  source_name: "Saisie manuelle",
  source_url: "",
  apply_channel: "",
  apply_instructions: "",
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
  // Photo FACULTATIVE de l'offre : choisie ici, envoyée après
  // l'enregistrement (l'identifiant de l'offre est alors connu).
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
        company: form.company,
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
        source_name: form.source_name || "Saisie manuelle",
        source_url: form.source_url,
        apply_channel: form.apply_channel || "",
        apply_instructions: form.apply_instructions || "",
        apply_email: form.apply_email || null,
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
        saved = await api(`/admin/jobs/${form.id}`, { method: "PUT", body: payload });
      } else {
        saved = await api("/admin/jobs", { method: "POST", body: payload });
      }
      const jobId = saved?.id || form.id;
      if (jobId && photoFile) {
        const fd = new FormData();
        fd.append("file", photoFile);
        await api(`/admin/jobs/${jobId}/photo`, { method: "POST", form: fd });
      } else if (jobId && removePhoto) {
        await api(`/admin/jobs/${jobId}/photo`, { method: "DELETE" });
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
          <input value={form.salary || ""} onChange={(e) => set("salary", e.target.value)} placeholder="300 000 à 500 000 FCFA" />
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
        domainLabel="Domaine de l'offre"
        specialtyLabel="Spécialité recherchée"
        onChange={({ domain_id, specialty_ids }) =>
          setForm((f) => ({
            ...f,
            domain_id,
            specialty_id: specialty_ids?.[0] ?? null,
          }))
        }
        hint="Le domaine alimente les filtres publics et la recherche des talents."
      />
      <label className="field">
        <span>Description</span>
        <textarea rows="3" value={form.description} onChange={(e) => set("description", e.target.value)} />
      </label>
      <label className="field">
        <span>Profil recherché</span>
        <textarea rows="2" value={form.requirements} onChange={(e) => set("requirements", e.target.value)} />
      </label>

      {/* Photo FACULTATIVE : elle illustre l'offre côté candidat. */}
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

      {/* Candidature : canal, instructions et e-mail du publieur.
          Renseignés, ils permettent la transmission automatique. */}
      <div className="grid-2">
        <label className="field">
          <span>Canal de candidature</span>
          <select value={form.apply_channel || ""} onChange={(e) => set("apply_channel", e.target.value)}>
            <option value="">Automatique (recruteur lié, sinon externe)</option>
            <option value="platform">Plateforme (compte recruteur lié)</option>
            <option value="external">Externe (site ou e-mail de l'entreprise)</option>
          </select>
        </label>
        <label className="field">
          <span>E-mail de candidature (transmission automatique)</span>
          <input
            value={form.apply_email || ""}
            onChange={(e) => set("apply_email", e.target.value)}
            placeholder="recrutement@entreprise.cm"
          />
        </label>
        <label className="field">
          <span>Mots-clés de routage e-mail</span>
          <input
            value={keywordsText}
            onChange={(e) => setKeywordsText(e.target.value)}
            placeholder="développeur, laravel, douala"
          />
          <span className="field-hint">
            Séparés par des virgules. La référence OS-XXXX reste prioritaire.
          </span>
        </label>
      </div>
      <p className="small muted">
        Référence publique de l'offre :{" "}
        <span className="job-reference">
          {form.email_reference || "attribuée après enregistrement"}
        </span>
      </p>
      <label className="field">
        <span>Instructions de candidature (affichées au candidat)</span>
        <textarea
          rows="2"
          value={form.apply_instructions || ""}
          onChange={(e) => set("apply_instructions", e.target.value)}
          placeholder="Ex. Postulez via le formulaire du site, puis envoyez une copie à recrutement@entreprise.cm en précisant la référence."
        />
      </label>
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
  const [query, setQuery] = useState("");
  const [contract, setContract] = useState("");
  const [source, setSource] = useState("");
  const location = useLocation();
  const navigate = useNavigate();

  async function importFromUrl(e) {
    e.preventDefault();
    setImporting(true);
    setImportError("");
    setImportNotice("");
    try {
      const draft = await api("/admin/import-url", { method: "POST", body: { url: importUrl } });
      fromParsed({ ...draft, source_url: importUrl }, "Import URL");
      setImportNotice("Brouillon extrait : vérifiez chaque champ avant d'enregistrer.");
      setImportUrl("");
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

  // Import depuis /admin/sources : le brouillon arrive par la navigation et
  // ouvre directement le formulaire d'offre prérempli.
  useEffect(() => {
    const draft = location.state?.draft;
    if (!draft) return;
    fromParsed(draft, "Import URL");
    navigate(location.pathname, { replace: true, state: null });
  }, [location.state, location.pathname, navigate]);

  if (error && !jobs) return <div className="page"><ErrorNote error={error} /></div>;
  if (!jobs) return <div className="page"><Loader /></div>;

  const sources = [...new Set(jobs.map((j) => j.source_name).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, "fr"));
  const needle = query.trim().toLowerCase();
  const visibleJobs = jobs.filter((j) => {
    if (contract && j.contract_type !== contract) return false;
    if (source && j.source_name !== source) return false;
    if (!needle) return true;
    return [
      j.title, j.company, j.location, j.sector, j.source_name, j.source_url,
    ].filter(Boolean).join(" ").toLowerCase().includes(needle);
  });

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

  function fromParsed(draft, sourceName = "Saisie assistée") {
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
      source_name: sourceName,
      source_url: draft.source_url || "",
      apply_channel: "",
      apply_instructions: "",
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

      {jobs.length > 0 && (
        <div className="filters">
          <label className="field">
            <span>Rechercher une offre</span>
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Poste, entreprise, ville, source…"
            />
          </label>
          <label className="field">
            <span>Contrat</span>
            <select value={contract} onChange={(e) => setContract(e.target.value)}>
              <option value="">Tous les contrats</option>
              {CONTRACT_TYPES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Source</span>
            <select value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="">Toutes les sources</option>
              {sources.map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          {(query || contract || source) && (
            <button
              type="button"
              className="btn btn-ghost btn-small"
              style={{ alignSelf: "end" }}
              onClick={() => { setQuery(""); setContract(""); setSource(""); }}
            >
              Réinitialiser
            </button>
          )}
          <p className="small muted" style={{ gridColumn: "1 / -1", margin: 0 }}>
            {visibleJobs.length} offre(s) affichée(s) sur {jobs.length}.
          </p>
        </div>
      )}

      <div className="table-wrap" style={{ marginTop: "1rem" }}>
        <table className="skills">
          <thead>
            <tr>
              <th>Offre</th>
              <th>Localisation</th>
              <th>Contrat</th>
              <th>Publiée le</th>
              <th>Échéance</th>
              <th>Source</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {visibleJobs.map((j) => (
              <tr key={j.id}>
                <td>
                  <strong>{j.title}</strong>
                  <div className="small muted">{j.company} · {j.sector}</div>
                </td>
                <td>{j.location}</td>
                <td>{j.contract_type}</td>
                <td>{fmtDate(j.published_at)}</td>
                <td>{j.deadline ? fmtDate(j.deadline) : "Aucune"}</td>
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
                    <button
                      className="btn btn-outline btn-small"
                      onClick={() => navigate(`/visuel/${j.id}`)}
                      title="Visuel de candidature pour LinkedIn"
                    >
                      Visuel
                    </button>
                    <button className="btn btn-danger btn-small" onClick={() => remove(j)}>
                      Supprimer
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {visibleJobs.length === 0 && (
              <tr>
                <td colSpan="7" className="small muted">
                  Aucune offre ne correspond à ces critères.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
