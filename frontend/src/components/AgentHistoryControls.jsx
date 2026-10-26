import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { Icon, I } from "./icons.jsx";

// Contrôles d'une conversation précise avec l'agent :
// - conservation 30 jours par défaut ;
// - bascule en mode éphémère ;
// - effacement immédiat de la conversation affichée.

export default function AgentHistoryControls({ conversationId, onUpdated, onDeleted }) {
  const [conversation, setConversation] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!conversationId) return;
    let alive = true;
    api(`/assistant/conversations/${conversationId}`)
      .then((data) => {
        if (!alive) return;
        setConversation(data.conversation || null);
      })
      .catch((err) => alive && setError(err.detail));
    return () => {
      alive = false;
    };
  }, [conversationId]);

  async function switchMode() {
    if (!conversation || busy) return;
    setBusy(true);
    setError("");
    try {
      const next = conversation.history_mode === "ephemeral" ? "persist" : "ephemeral";
      const data = await api(`/assistant/conversations/${conversation.id}`, {
        method: "PUT",
        body: { history_mode: next },
      });
      setConversation(data);
      if (onUpdated) onUpdated(data);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function clear() {
    if (!conversation || busy) return;
    if (!window.confirm(`Effacer la conversation « ${conversation.title} » ?`)) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(`/assistant/conversations/${conversation.id}`, { method: "DELETE" });
      if (onDeleted) onDeleted(conversation.id);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  if (!conversation) return null;

  return (
    <div className="ag-history">
      <div className="ag-history-head">
        <span className="ag-history-icon"><Icon d={I.clock} size={15} /></span>
        <div>
          <h3>Historique de cette conversation</h3>
          <p>
            {conversation.history_mode === "ephemeral"
              ? "Mode éphémère : vos nouveaux échanges ne sont pas conservés."
              : `Conservé ${conversation.retention_days} jours, puis supprimé automatiquement.`}
          </p>
        </div>
      </div>
      <div className="ag-history-actions">
        <button
          type="button"
          className="btn btn-outline btn-small"
          onClick={switchMode}
          disabled={busy}
        >
          {conversation.history_mode === "ephemeral"
            ? "Revenir à l'historique conservé"
            : "Passer en mode éphémère"}
        </button>
        <button
          type="button"
          className="btn btn-remove btn-small"
          onClick={clear}
          disabled={busy}
        >
          Effacer cette conversation
        </button>
      </div>
      {error && <div className="alert alert-error small">{error}</div>}
    </div>
  );
}
