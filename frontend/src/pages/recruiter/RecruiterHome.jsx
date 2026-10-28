import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../api/client.js";
import { STATUS_LABELS, statusTone } from "../../lib.js";
import Avatar from "../../components/Avatar.jsx";
import ContactDialog from "../../components/ContactDialog.jsx";
import TalentCard from "../../components/TalentCard.jsx";
import VerifiedBadge from "../../components/VerifiedBadge.jsx";
import { Loader, ErrorNote } from "../../components/ui.jsx";

// Dashboard recruteur (§37) : entreprise, offres publiées, profils
// disponibles avec contact direct via la messagerie, statut PARTAGÉ
// des candidatures reçues.

// Transitions réellement autorisées au recruteur. Le candidat garde la
// main sur l'envoi, l'acceptation et le retrait ; le recruteur instruit.
const RECRUITER_NEXT = {
  envoyee: "en_attente",
  en_attente: "entretien",
  entretien: "offre",
};
const REFUSABLE = new Set(["envoyee", "en_attente", "entretien", "offre"]);

export default function RecruiterHome() {
  const [company, setCompany] = useState(null);
  const [jobs, setJobs] = useState(null);
  const [applications, setApplications] = useState(null);
  const [candidates, setCandidates] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [contactTarget, setContactTarget] = useState(null);
  const [editingCompany, setEditingCompany] = useState(false);
  const [companyForm, setCompanyForm] = useState(null);
  const [companyError, setCompanyError] = useState("");
  const [companyBusy, setCompanyBusy] = useState(false);
  const [busyApp, setBusyApp] = useState(0);
  const [refuseFor, setRefuseFor] = useState(null);
  const [refuseReason, setRefuseReason] = useState("");
  const [searchParams] = useSearchParams();

  useEffect(() => {
    api("/recruiter/company").then(setCompany).catch((e) => setError(e.detail));
    api("/recruiter/jobs").then(setJobs).catch(() => setJobs([]));
    api("/recruiter/applications").then(setApplications).catch(() => setApplications([]));
    api("/recruiter/candidates").then(setCandidates).catch(() => setCandidates([]));
  }, []);

  // Le profil de l'entreprise est modifiable sans quitter le tableau de bord.
  function openCompanyEdit() {
    setCompanyForm({
      name: company.name || "",
      sector: company.sector || "",
      location: company.location || "",
      website: company.website || "",
      description: company.description || "",
    });
    setCompanyError("");
    setEditingCompany(true);
  }

  async function saveCompany(event) {
    event.preventDefault();
    if (!companyForm.name.trim()) {
      setCompanyError("Le nom de l'entreprise est obligatoire.");
      return;
    }
    setCompanyBusy(true);
    setCompanyError("");
    try {
      const updated = await api("/recruiter/company", {
        method: "PUT",
        body: { ...companyForm, name: companyForm.name.trim() },
      });
      setCompany(updated);
      setEditingCompany(false);
      setNotice("Profil de l'entreprise mis à jour.");
    } catch (err) {
      setCompanyError(err.detail);
    } finally {
      setCompanyBusy(false);
    }
  }

  async function advanceApplication(app) {
    const next = RECRUITER_NEXT[app.status];
    if (!next) return;
    setBusyApp(app.id);
    setError("");
    try {
      await api(`/recruiter/applications/${app.id}`, {
        method: "PATCH",
        body: { status: next },
      });
      setNotice(`Candidature de ${app.candidate_name} passée à « ${STATUS_LABELS[next]} ».`);
      const updated = await api("/recruiter/applications");
      setApplications(updated);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusyApp(0);
    }
  }

  async function confirmRefusal(app) {
    setBusyApp(app.id);
    setError("");
    try {
      await api(`/recruiter/applications/${app.id}`, {
        method: "PATCH",
        body: { status: "refusee", reason: refuseReason.trim() },
      });
      setNotice(`Candidature de ${app.candidate_name} refusée.`);
      setRefuseFor(null);
      setRefuseReason("");
      const updated = await api("/recruiter/applications");
      setApplications(updated);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusyApp(0);
    }
  }

  if (error && !company) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!company || !jobs || !applications || !candidates) {
    return <div className="page"><Loader /></div>;
  }

  const jobFilter = searchParams.get("offre");
  const filterJob = jobFilter ? jobs.find((j) => String(j.id) === jobFilter) : null;
  const visibleApplications = jobFilter
    ? applications.filter((a) => String(a.job_id) === jobFilter)
    : applications;

  return (
    <div className="page">
      <div className="profile-card">
        <div className="talent-avatar" style={{ background: "var(--accent)", fontSize: "1.4rem", width: "64px", height: "64px" }}>
          {company.name.split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase()}
        </div>
        <div style={{ flex: 1 }}>
          <h1 style={{ marginBottom: 0 }}>{company.name}</h1>
          <p className="job-meta" style={{ margin: "0.2rem 0" }}>
            {company.sector || "Entreprise"}
            {company.location ? ` · ${company.location}` : ""}
          </p>
          {company.description && (
            <p className="small muted" style={{ margin: 0, maxWidth: "46rem" }}>
              {company.description}
            </p>
          )}
          <div className="company-links">
            {company.website && (
              <a href={company.website} target="_blank" rel="noreferrer" className="small">
                Site web de l'entreprise
              </a>
            )}
            <button type="button" className="btn btn-outline btn-small" onClick={openCompanyEdit}>
              Modifier l'entreprise
            </button>
          </div>
        </div>
      </div>

      {editingCompany && companyForm && (
        <form className="panel" onSubmit={saveCompany}>
          <h2>Profil de l'entreprise</h2>
          <p className="small muted">
            Ces informations identifient vos offres auprès des candidats.
          </p>
          <div className="grid-2">
            <label className="field">
              <span>Nom de l'entreprise *</span>
              <input
                value={companyForm.name}
                onChange={(e) => setCompanyForm({ ...companyForm, name: e.target.value })}
                required
              />
            </label>
            <label className="field">
              <span>Secteur</span>
              <input
                value={companyForm.sector}
                onChange={(e) => setCompanyForm({ ...companyForm, sector: e.target.value })}
                placeholder="Ex. Informatique / IT"
              />
            </label>
            <label className="field">
              <span>Localisation</span>
              <input
                value={companyForm.location}
                onChange={(e) => setCompanyForm({ ...companyForm, location: e.target.value })}
                placeholder="Douala"
              />
            </label>
            <label className="field">
              <span>Site web</span>
              <input
                value={companyForm.website}
                onChange={(e) => setCompanyForm({ ...companyForm, website: e.target.value })}
                placeholder="https://…"
              />
            </label>
          </div>
          <label className="field">
            <span>Description</span>
            <textarea
              rows="3"
              value={companyForm.description}
              onChange={(e) => setCompanyForm({ ...companyForm, description: e.target.value })}
            />
          </label>
          <ErrorNote error={companyError} />
          <div className="actions-row">
            <button className="btn btn-primary" disabled={companyBusy}>
              {companyBusy ? "Enregistrement…" : "Enregistrer"}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setEditingCompany(false)}
              disabled={companyBusy}
            >
              Annuler
            </button>
          </div>
        </form>
      )}
      <ErrorNote error={error} />
      {notice && <div className="alert alert-success">{notice}</div>}

      <div className="metric-strip">
        <div className="metric">
          <strong>{jobs.length}</strong>
          <span>offre(s) publiée(s)</span>
        </div>
        <div className="metric">
          <strong>{applications.length}</strong>
          <span>candidature(s) reçue(s)</span>
        </div>
        <div className="metric">
          <strong>{candidates.length}</strong>
          <span>profil(s) disponible(s)</span>
        </div>
      </div>

      <section className="section">
        <div className="section-head">
          <h2>Prochaines actions</h2>
        </div>
        <div className="actions-row">
          <Link className="btn btn-primary" to="/recruteur/offres">Publier une offre</Link>
          <Link className="btn btn-outline" to="/recruteur/candidats">Rechercher des talents</Link>
          <Link className="btn btn-ghost" to="/messages">Boîte de réception</Link>
        </div>
      </section>

      {(applications.length > 0 || jobFilter) && (
        <section className="section" id="candidatures">
          <div className="section-head">
            <h2>Candidatures reçues ({visibleApplications.length})</h2>
          </div>
          {jobFilter && (
            <p className="small muted" style={{ margin: "0 0 0.5rem" }}>
              {filterJob ? `Offre : ${filterJob.title}` : `Offre #${jobFilter}`}
              {" · "}
              <Link className="link-more" to="/recruteur#candidatures">
                Toutes les offres
              </Link>
            </p>
          )}
          {visibleApplications.length === 0 && (
            <p className="muted">Aucune candidature pour cette offre.</p>
          )}
          {visibleApplications.map((a) => (
            <div className="app-row" key={a.id}>
              <div className="app-head">
                <div className="app-candidate">
                  <Avatar
                    name={a.candidate_name}
                    photoUrl={a.candidate_photo_url}
                    className="app-avatar"
                  />
                  <div>
                    <strong>{a.candidate_name}</strong>
                    {a.candidate_verified && (
                      <VerifiedBadge label="Profil vérifié" size={13} className="verified-inline" />
                    )}
                    <p className="job-meta" style={{ margin: "0.15rem 0" }}>
                      Postule à : {a.job_title} ·{" "}
                      <span className={`apps-status ${statusTone(a.status)}`}>
                        {STATUS_LABELS[a.status] || a.status}
                      </span>
                    </p>
                  </div>
                </div>
                <div className="actions-row" style={{ marginTop: 0 }}>
                  {RECRUITER_NEXT[a.status] && (
                    <button
                      className="btn btn-primary btn-small"
                      onClick={() => advanceApplication(a)}
                      disabled={busyApp === a.id}
                    >
                      Passer à « {STATUS_LABELS[RECRUITER_NEXT[a.status]]} »
                    </button>
                  )}
                  {REFUSABLE.has(a.status) && (
                    <button
                      className="btn btn-remove btn-small"
                      onClick={() => {
                        setRefuseFor(a.id);
                        setRefuseReason("");
                      }}
                      disabled={busyApp === a.id}
                    >
                      Refuser
                    </button>
                  )}
                  <button
                    className="btn btn-outline btn-small"
                    onClick={() => setContactTarget({ user_id: a.candidate_id, full_name: a.candidate_name })}
                  >
                    Contacter
                  </button>
                </div>
              </div>
              {refuseFor === a.id && (
                <form
                  className="app-refuse"
                  onSubmit={(event) => {
                    event.preventDefault();
                    confirmRefusal(a);
                  }}
                >
                  <label className="field">
                    <span>Motif du refus (facultatif, visible par le candidat)</span>
                    <input
                      value={refuseReason}
                      onChange={(event) => setRefuseReason(event.target.value)}
                      maxLength={1000}
                      placeholder="Ex. profil incomplet pour le poste"
                    />
                  </label>
                  <div className="actions-row" style={{ marginTop: 0 }}>
                    <button
                      className="btn btn-remove btn-small"
                      disabled={busyApp === a.id}
                    >
                      {busyApp === a.id ? "Envoi…" : "Confirmer le refus"}
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-small"
                      onClick={() => {
                        setRefuseFor(null);
                        setRefuseReason("");
                      }}
                      disabled={busyApp === a.id}
                    >
                      Annuler
                    </button>
                  </div>
                </form>
              )}
              {a.apply_channel === "external" && (
                <div className="app-external">
                  <span className="app-external-label">
                    Candidature déposée sur le site de l'entreprise
                  </span>
                  <div className="actions-row" style={{ marginTop: 0 }}>
                    {a.apply_url && (
                      <a
                        className="btn btn-outline btn-small"
                        href={a.apply_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Voir l'offre et postuler
                      </a>
                    )}
                    {a.apply_email && (
                      <a className="btn btn-ghost btn-small" href={`mailto:${a.apply_email}`}>
                        Écrire à {a.apply_email}
                      </a>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </section>
      )}

      <section className="section">
        <div className="section-head">
          <h2>Profils disponibles</h2>
          <Link className="small" to="/recruteur/candidats">Recherche avancée →</Link>
        </div>
        {candidates.slice(0, 5).map((c) => (
          <TalentCard
            key={c.user_id}
            candidate={c}
            profileHref={`/recruteur/candidats/${c.user_id}`}
            onContact={setContactTarget}
          />
        ))}
        {candidates.length === 0 && (
          <p className="muted">Aucun profil candidat disponible pour l'instant.</p>
        )}
      </section>

      {contactTarget && (
        <ContactDialog candidate={contactTarget} onClose={() => setContactTarget(null)} />
      )}
    </div>
  );
}
