import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { ErrorNote } from "./ui.jsx";

// Contact d'un candidat via la messagerie interne. Aucune coordonnée
// personnelle n'est exposée : le message part dans la conversation.
export default function ContactDialog({ candidate, onClose }) {
  const [body, setBody] = useState(
    "Bonjour, votre profil correspond à l'un de nos postes. Êtes-vous disponible pour un échange ?"
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    function onKey(event) {
      if (event.key === "Escape" && !busy) onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  async function send(event) {
    event.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    setError("");
    try {
      await api("/messages", {
        method: "POST",
        body: { recipient_id: candidate.user_id, body: body.trim() },
      });
      navigate(`/messages/${candidate.user_id}`);
    } catch (err) {
      setError(err.detail);
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
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="contact-title">
        <h2 id="contact-title">Contacter {candidate.full_name || "ce candidat"}</h2>
        <p className="small muted">
          Le message est envoyé dans la messagerie interne. Le candidat garde
          la maîtrise de ses coordonnées personnelles.
        </p>
        <form onSubmit={send}>
          <label className="field">
            <span>Message *</span>
            <textarea
              ref={inputRef}
              rows="5"
              value={body}
              onChange={(event) => setBody(event.target.value)}
            />
          </label>
          <ErrorNote error={error} />
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={busy}>
              Annuler
            </button>
            <button className="btn btn-primary" disabled={busy || !body.trim()}>
              {busy ? "Envoi…" : "Envoyer le message"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
