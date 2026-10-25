import { useEffect, useRef, useState } from "react";
import { api, resourceHref } from "../api/client.js";
import { fmtDate } from "../lib.js";
import { ErrorNote } from "./ui.jsx";

// Invitation à un entretien depuis une shortlist : offre, date, heure,
// durée, objet et message personnalisable. Le backend ajoute l'identité
// réelle du poste et de l'entreprise, le créneau lisible et les liens
// profonds (accepter / demander un autre créneau).
export default function InterviewInviteDialog({ candidate, onClose, onSent }) {
  const [jobs, setJobs] = useState([]);
  const [jobId, setJobId] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("10:00");
  const [duration, setDuration] = useState(45);
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState(
    "Bonjour,\n\nVotre profil a retenu notre attention pour ce poste. "
    + "Nous aimerions vous rencontrer pour un entretien.\n\n"
    + "Merci de confirmer le créneau proposé ci-dessous.\n\nCordialement,"
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(null);
  const firstRef = useRef(null);

  useEffect(() => {
    api("/recruiter/jobs")
      .then((list) => {
        const rows = list || [];
        setJobs(rows);
        if (rows.length === 1) setJobId(String(rows[0].id));
      })
      .catch((e) => setError(e.detail));
  }, []);

  useEffect(() => {
    firstRef.current?.focus();
  }, []);

  useEffect(() => {
    function onKey(event) {
      if (event.key === "Escape" && !busy) onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  const selectedJob = jobs.find((j) => String(j.id) === String(jobId));

  useEffect(() => {
    if (!selectedJob) return;
    setSubject((current) => (
      current.trim() ? current : `Entretien pour le poste de ${selectedJob.title}`
    ));
  }, [selectedJob]);

  async function send(event) {
    event.preventDefault();
    if (!jobId || !date || !time) {
      setError("Choisissez l'offre, la date et l'heure du créneau.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const row = await api("/recruiter/interviews", {
        method: "POST",
        body: {
          candidate_id: candidate.user_id,
          job_id: Number(jobId),
          slot_at: `${date}T${time}:00`,
          duration_min: Number(duration),
          subject: subject.trim(),
          message: message.trim(),
        },
      });
      setSent(row);
      onSent?.(row);
    } catch (err) {
      setError(err.detail || "Envoi impossible");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <div className="modal modal-wide" role="dialog" aria-modal="true" aria-labelledby="invite-title">
        <h2 id="invite-title">Inviter {candidate.full_name || "ce candidat"} en entretien</h2>
        <p className="small muted">
          L'e-mail reprend l'identité exacte de l'offre et de l'entreprise,
          le créneau et deux liens : accepter ou demander un autre créneau.
          Aucune information n'est inventée.
        </p>

        {sent ? (
          <div className="invite-sent">
            <div className="alert alert-success">
              Invitation enregistrée pour le {fmtDate(sent.slot_at)}.
            </div>
            <p className="small muted">
              {sent.email_sent
                ? "L'e-mail a été envoyé au candidat avec les liens de réponse et le fichier calendrier (.ics) joint."
                : "Le service e-mail n'est pas configuré : l'invitation reste disponible dans l'espace du candidat, rubrique Entretiens."}
            </p>
            <div className="modal-actions">
              <a
                className="btn btn-outline"
                href={resourceHref(sent.calendar_url)}
              >
                Calendrier (.ics)
              </a>
              <button type="button" className="btn btn-primary" onClick={onClose}>
                Fermer
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={send}>
            <label className="field">
              <span>Offre concernée *</span>
              <select ref={firstRef} value={jobId} onChange={(e) => setJobId(e.target.value)} required>
                <option value="">Choisir une de vos offres</option>
                {jobs.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title} · {job.location}
                  </option>
                ))}
              </select>
            </label>
            {jobs.length === 0 && (
              <p className="small muted">
                Publiez d'abord une offre : l'invitation doit citer un poste réel.
              </p>
            )}

            <div className="invite-grid">
              <label className="field">
                <span>Date *</span>
                <input
                  type="date"
                  value={date}
                  min={new Date().toISOString().slice(0, 10)}
                  onChange={(e) => setDate(e.target.value)}
                  required
                />
              </label>
              <label className="field">
                <span>Heure *</span>
                <input
                  type="time"
                  value={time}
                  onChange={(e) => setTime(e.target.value)}
                  required
                />
              </label>
              <label className="field">
                <span>Durée</span>
                <select value={duration} onChange={(e) => setDuration(e.target.value)}>
                  <option value={30}>30 minutes</option>
                  <option value={45}>45 minutes</option>
                  <option value={60}>1 heure</option>
                  <option value={90}>1 h 30</option>
                </select>
              </label>
            </div>

            <label className="field">
              <span>Objet de l'e-mail *</span>
              <input
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                maxLength={200}
                required
              />
            </label>
            <label className="field">
              <span>Message personnalisé *</span>
              <textarea
                rows={6}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                maxLength={4000}
                required
              />
            </label>

            <ErrorNote error={error} />
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={onClose} disabled={busy}>
                Annuler
              </button>
              <button
                className="btn btn-primary"
                disabled={busy || jobs.length === 0 || !jobId || !date || message.trim().length < 20}
              >
                {busy ? "Envoi…" : "Envoyer l'invitation"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
