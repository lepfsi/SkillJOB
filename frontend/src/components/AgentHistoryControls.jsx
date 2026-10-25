import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { Icon, I } from "./icons.jsx";

// Contrôle réel de l'historique de conversation avec l'agent :
// - conservation 30 jours par défaut ;
// - bascule en mode éphémère (aucune nouvelle trace en base) ;
// - effacement immédiat par l'utilisateur.

export default function AgentHistoryControls() {
  const [mode, setMode] = useState("persist");
  const [retentionDays, setRetentionDays] = useState(30);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    api("/assistant/history")
      .then((data) => {
        if (!alive) return;
        setMode(data.mode || "persist");
        setRetentionDays(data.retention_days || 30);
      })
      .catch((err) => alive && setError(err.detail));
    return () => {
      alive = false;
    };
  }, []);

  async function switchMode() {
    setBusy(true);
    setError("");
    try {
      const next = mode === "persist" ? "ephemeral" : "persist";
      const data = await api("/assistant/history/settings", {
        method: "PUT",
        body: { mode: next },
      });
      setMode(data.mode || next);
      setRetentionDays(data.retention_days || 30);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function clear() {
    if (!window.confirm(
      "Effacer l'historique de conversation avec l'agent ?"
    )) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api("/assistant/history", { method: "DELETE" });
      window.dispatchEvent(new Event("orientskill:history-cleared"));
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ag-history">
      <div className="ag-history-head">
        <span className="ag-history-icon"><Icon d={I.clock} size={15} /></span>
        <div>
          <h3>Historique de conversation</h3>
          <p>
            {mode === "ephemeral"
              ? "Mode éphémère : vos nouveaux échanges ne sont pas conservés. Les anciens restent jusqu'à effacement."
              : `Conservé ${retentionDays} jours, puis supprimé automatiquement.`}
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
          {mode === "ephemeral"
            ? "Revenir à l'historique conservé"
            : "Passer en mode éphémère"}
        </button>
        <button
          type="button"
          className="btn btn-remove btn-small"
          onClick={clear}
          disabled={busy}
        >
          Effacer l'historique
        </button>
      </div>
      {error && <div className="alert alert-error small">{error}</div>}
    </div>
  );
}
