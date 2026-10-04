import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import { fmtDate, STATUS_ORDER, STATUS_LABELS } from "../../lib.js";
import MatchBadge from "../../components/MatchBadge.jsx";
import { Loader, ErrorNote } from "../../components/ui.jsx";

// Dashboard recruteur (§37) : entreprise, offres publiées, profils
// disponibles avec contact direct via la messagerie, statut PARTAGÉ
// des candidatures reçues.

const NEXT_STATUS = {
  identifiee: "cv_prepare",
  cv_prepare: "envoyee",
  envoyee: "en_attente",
  en_attente: "entretien",
  entretien: "offre",
  offre: "acceptee",
};

export default function RecruiterHome() {
  const [company, setCompany] = useState(null);
  const [jobs, setJobs] = useState(null);
  const [applications, setApplications] = useState(null);
  const [candidates, setCandidates] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    api("/recruiter/company").then(setCompany).catch((e) => setError(e.detail));
    api("/recruiter/jobs").then(setJobs).catch(() => setJobs([]));
    api("/recruiter/applications").then(setApplications).catch(() => setApplications([]));
    api("/recruiter/candidates").then(setCandidates).catch(() => setCandidates([]));
  }, []);

  async function contact(candidateId) {
    const body = window.prompt(
      "Message au candidat (envoyé via la messagerie OrientSkill) :",
      "Bonjour, votre profil correspond à l'un de nos postes. Êtes-vous disponible pour un échange ?"
    );
    if (!body) return;
    try {
      await api("/messages", { method: "POST", body: { recipient_id: candidateId, body } });
      window.location.href = `/messages/${candidateId}`;
    } catch (err) {
      setError(err.detail);
    }
  }

  async function advanceApplication(app) {
    const next = NEXT_STATUS[app.status];
    if (!next) return;
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
    }
  }

  if (error && !company) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!company || !jobs || !applications || !candidates) {
    return <div className="page"><Loader /></div>;
  }

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
        </div>
      </div>
      <ErrorNote error={error} />

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

      {applications.length > 0 && (
        <section className="section">
          <h2>Candidatures reçues</h2>
          {notice && <div className="alert alert-success">{notice}</div>}
          {applications.map((a) => (
            <div className="app-row" key={a.id}>
              <div className="app-head">
                <div>
                  <strong>{a.candidate_name}</strong>
                  {a.candidate_verified && <span className="verified-chip" style={{ marginLeft: "0.5rem" }}>Profil vérifié</span>}
                  <p className="job-meta" style={{ margin: "0.15rem 0" }}>
                    Postule à : {a.job_title} · statut : {STATUS_LABELS[a.status] || a.status}
                  </p>
                </div>
                <div className="actions-row" style={{ marginTop: 0 }}>
                  {NEXT_STATUS[a.status] && (
                    <button className="btn btn-primary btn-small" onClick={() => advanceApplication(a)}>
                      Passer à « {STATUS_LABELS[NEXT_STATUS[a.status]]} »
                    </button>
                  )}
                  <button className="btn btn-outline btn-small" onClick={() => contact(a.candidate_id)}>
                    Contacter
                  </button>
                </div>
              </div>
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
          <div className="talent-card" key={c.user_id}>
            <div className="talent-card-header">
              <div className="talent-avatar">
                {c.full_name.split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase()}
              </div>
              <div className="talent-card-id">
                <strong style={{ fontSize: "1.02rem" }}>{c.full_name}</strong>
                <p className="job-meta" style={{ margin: "0.1rem 0" }}>
                  {c.title || "Profil en construction"} · {c.location || "Cameroun"}
                </p>
              </div>
              {c.verified ? (
                <span className="verified-chip">Vérifié</span>
              ) : (
                <span className="badge badge-none">Non vérifié</span>
              )}
            </div>
            {c.summary && <p className="talent-summary">{c.summary}</p>}
            <div className="talent-actions">
              <Link className="btn btn-outline btn-small" to={`/recruteur/candidats/${c.user_id}`}>
                Voir la carte de profil
              </Link>
              <button className="btn btn-primary btn-small" onClick={() => contact(c.user_id)}>
                Contacter
              </button>
            </div>
          </div>
        ))}
        {candidates.length === 0 && (
          <p className="muted">Aucun profil candidat disponible pour l'instant.</p>
        )}
      </section>
    </div>
  );
}
