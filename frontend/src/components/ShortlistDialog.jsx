import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { ErrorNote, Loader } from "./ui.jsx";

// Choix d'une shortlist existante, ou création d'une nouvelle liste,
// puis ajout du candidat. Les listes sont rechargées à l'ouverture pour
// rester à jour même après une création dans un autre onglet.
export default function ShortlistDialog({ candidate, onClose, onDone }) {
  const [lists, setLists] = useState(null);
  const [selectedId, setSelectedId] = useState("");
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/recruiter/shortlists")
      .then((data) => {
        setLists(data);
        setSelectedId(data[0]?.id ? String(data[0].id) : "");
      })
      .catch((err) => {
        setLists([]);
        setError(err.detail);
      });
  }, []);

  useEffect(() => {
    function onKey(event) {
      if (event.key === "Escape" && !busy) onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  async function add(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      let targetId = selectedId;
      if (!targetId && newName.trim()) {
        const created = await api("/recruiter/shortlists", {
          method: "POST",
          body: { name: newName.trim() },
        });
        targetId = String(created.id);
      }
      if (!targetId) {
        setError("Choisissez une shortlist ou donnez-lui un nom.");
        setBusy(false);
        return;
      }
      await api(`/recruiter/shortlists/${targetId}/items`, {
        method: "POST",
        body: { candidate_id: candidate.user_id },
      });
      onDone?.();
      onClose();
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
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="shortlist-title">
        <h2 id="shortlist-title">Ajouter {candidate.full_name || "ce candidat"} à une shortlist</h2>
        <p className="small muted">
          Les shortlists restent privées à votre entreprise.
        </p>
        <form onSubmit={add}>
          {!lists && <Loader />}
          {lists && lists.length > 0 && (
            <div className="shortlist-choices" role="radiogroup" aria-label="Shortlists existantes">
              {lists.map((list) => (
                <label className="check" key={list.id}>
                  <input
                    type="radio"
                    name="shortlist"
                    checked={selectedId === String(list.id)}
                    onChange={() => {
                      setSelectedId(String(list.id));
                      setNewName("");
                    }}
                  />
                  {list.name}
                  <span className="small muted">
                    ({list.items?.length || 0} candidat{list.items?.length > 1 ? "s" : ""})
                  </span>
                </label>
              ))}
            </div>
          )}
          <label className="field">
            <span>{lists && lists.length > 0 ? "Ou créer une nouvelle liste" : "Créer une liste"}</span>
            <input
              value={newName}
              onChange={(event) => {
                setNewName(event.target.value);
                if (event.target.value) setSelectedId("");
              }}
              placeholder="Ex. Techniciens réseau"
            />
          </label>
          <ErrorNote error={error} />
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={busy}>
              Annuler
            </button>
            <button
              className="btn btn-primary"
              disabled={busy || (!selectedId && !newName.trim())}
            >
              {busy ? "Ajout…" : "Ajouter à la shortlist"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
