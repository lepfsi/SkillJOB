import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import { fmtDateTime } from "../../lib.js";
import { ArrowIcon } from "../../components/icons.jsx";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";

// File dédiée des demandes d'autre créneau. Le recruteur peut accepter un
// créneau proposé par le candidat, proposer une nouvelle date ou refuser.
// Chaque décision est tracée et notifiée au candidat.

const HISTORY_LABELS = {
  invited: "Invitation envoyée",
  accepted: "Créneau accepté par le candidat",
  declined: "Autre créneau demandé",
  refused: "Entretien refusé par le candidat",
  request_accepted: "Créneau accepté par le recruteur",
  slot_proposed: "Nouveau créneau proposé",
  request_refused: "Demande refusée",
};

function RequestCard({ request, onDone }) {
  const [slot, setSlot] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function act(action, slotAt = null) {
    if (action === "refuse" && !window.confirm(
      "Refuser cette demande met fin au processus d'entretien. Confirmer ?"
    )) {
      return;
    }
    setBusy(action);
    setError("");
    try {
      const row = await api(`/recruiter/interviews/${request.id}/respond`, {
        method: "POST",
        body: {
          action,
          slot_at: slotAt,
          note: note.trim(),
        },
      });
      onDone(row);
    } catch (err) {
      setError(err.detail || "Décision impossible");
    } finally {
      setBusy("");
    }
  }

  function propose() {
    if (!slot) {
      setError("Choisissez une date et une heure pour le nouveau créneau.");
      return;
    }
    act("propose", `${slot}:00`);
  }

  return (
    <section className="dash-card request-card">
      <div className="request-head">
        <div>
          <span className="invite-badge invite-declined">Autre créneau demandé</span>
          <h2>{request.candidate_name}</h2>
          <p className="muted" style={{ margin: 0 }}>
            {request.job_title}
            {request.company ? ` · ${request.company}` : ""}
          </p>
        </div>
        <span className="small muted">
          Demande reçue le {fmtDateTime(request.responded_at)}
        </span>
      </div>

      <ul className="invite-facts">
        <li><span>Créneau initial</span><strong>{fmtDateTime(request.slot_at)}</strong></li>
        <li><span>Durée</span><strong>{request.duration_min} minutes</strong></li>
        <li><span>Candidat</span><strong>{request.candidate_name}</strong></li>
      </ul>

      {request.candidate_note && (
        <div className="invite-message">
          <h3>Message du candidat</h3>
          <p style={{ whiteSpace: "pre-line" }}>{request.candidate_note}</p>
        </div>
      )}

      <h3 className="request-subtitle">Créneaux proposés par le candidat</h3>
      {request.requested_slots?.length > 0 ? (
        <div className="request-slots">
          {request.requested_slots.map((value) => (
            <div className="request-slot" key={value}>
              <strong>{fmtDateTime(value)}</strong>
              <button
                type="button"
                className="btn btn-primary btn-small"
                disabled={!!busy}
                onClick={() => act("accept_requested", value)}
              >
                {busy === "accept_requested" ? "Confirmation…" : "Accepter ce créneau"}
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="small muted">
          Aucun créneau lisible n'accompagne cette demande : proposez une
          nouvelle date ci-dessous.
        </p>
      )}

      <div className="request-propose">
        <label className="field">
          <span>Proposer un autre créneau</span>
          <input
            type="datetime-local"
            value={slot}
            onChange={(e) => setSlot(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="btn btn-outline btn-small"
          disabled={!!busy || !slot}
          onClick={propose}
        >
          {busy === "propose" ? "Envoi…" : "Proposer ce créneau"}
        </button>
      </div>

      <label className="field">
        <span>Message au candidat (facultatif)</span>
        <textarea
          rows="2"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={1000}
          placeholder="Précisez le lieu, le format ou une information utile."
        />
      </label>

      <ErrorNote error={error} />

      <div className="actions-row">
        <button
          type="button"
          className="btn btn-remove btn-small"
          disabled={!!busy}
          onClick={() => act("refuse")}
        >
          {busy === "refuse" ? "Refus…" : "Refuser la demande"}
        </button>
        <Link className="btn btn-ghost btn-small" to="/recruteur/shortlists">
          Voir les shortlists
        </Link>
      </div>

      {request.history?.length > 0 && (
        <div className="invite-history">
          <h3>Historique</h3>
          <ol>
            {request.history.map((entry, index) => (
              <li key={`${entry.at}-${index}`}>
                <strong>{HISTORY_LABELS[entry.action] || entry.action}</strong>
                <span className="small muted">
                  {fmtDateTime(entry.at)}
                  {entry.slot_at ? ` · ${fmtDateTime(entry.slot_at)}` : ""}
                </span>
                {entry.note && <p className="small">{entry.note}</p>}
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}

export default function RecruiterInterviewRequests() {
  const [requests, setRequests] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    api("/recruiter/interviews/requests")
      .then((rows) => setRequests(rows || []))
      .catch((e) => setError(e.detail));
  }, []);

  if (error && !requests) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!requests) return <div className="page"><Loader /></div>;

  function done(row) {
    setRequests((rows) => rows.filter((item) => item.id !== row.id));
    setNotice(
      row.status === "accepted"
        ? "Créneau accepté : le candidat est notifié et l'entretien est confirmé."
        : row.status === "pending"
          ? "Nouveau créneau proposé : le candidat peut maintenant répondre."
          : "Demande refusée : le candidat est notifié."
    );
  }

  return (
    <div className="page">
      <Link className="back-link" to="/recruteur">
        <ArrowIcon direction="left" size={12} /> Accueil recruteur
      </Link>
      <h1>Demandes de créneau</h1>
      <p className="page-lead">
        Les candidats qui ne peuvent pas honorer le créneau proposé indiquent
        ici leurs disponibilités. Acceptez un créneau, proposez-en un autre ou
        refusez la demande. Chaque décision est notifiée au candidat.
      </p>

      {notice && <div className="alert alert-success">{notice}</div>}
      <ErrorNote error={error} />

      {requests.length === 0 ? (
        <Empty title="Aucune demande en attente">
          <p>
            Les demandes d'autre créneau apparaîtront ici, avec l'historique
            des échanges. Les invitations envoyées restent visibles dans les
            shortlists.
          </p>
          <Link className="btn btn-outline btn-small" to="/recruteur/shortlists">
            Voir mes shortlists <ArrowIcon direction="right" size={12} />
          </Link>
        </Empty>
      ) : (
        <>
          <p className="small muted">
            {requests.length} demande{requests.length > 1 ? "s" : ""} en attente.
          </p>
          {requests.map((request) => (
            <RequestCard key={request.id} request={request} onDone={done} />
          ))}
        </>
      )}
    </div>
  );
}
