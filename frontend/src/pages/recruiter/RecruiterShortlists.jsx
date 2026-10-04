import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client.js";
import { fmtDate } from "../../lib.js";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";

// Shortlists (§20, V2) : listes de candidats présélectionnés par le
// recruteur, isolées entre entreprises.

function ShortlistCard({ sl, onChanged }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);

  async function removeItem(candidateId) {
    setBusy(true);
    try {
      await api(`/recruiter/shortlists/${sl.id}/items/${candidateId}`, { method: "DELETE" });
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  async function contact(candidateId) {
    const body = window.prompt(
      "Message au candidat :",
      "Bonjour, vous figurez sur notre présélection. Êtes-vous disponible pour un échange ?"
    );
    if (!body) return;
    try {
      await api("/messages", { method: "POST", body: { recipient_id: candidateId, body } });
      navigate(`/messages/${candidateId}`);
    } catch {
      // la page messages affichera l'erreur
    }
  }

  async function removeList() {
    if (!window.confirm(`Supprimer la shortlist « ${sl.name} » ?`)) return;
    setBusy(true);
    try {
      await api(`/recruiter/shortlists/${sl.id}`, { method: "DELETE" });
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <div className="section-head">
        <h2 style={{ margin: 0 }}>{sl.name}</h2>
        <span className="small muted">
          créée le {fmtDate(sl.created_at)} · {sl.items.length} candidat(s)
        </span>
      </div>
      {sl.note && <p className="small muted">{sl.note}</p>}
      {sl.items.length === 0 ? (
        <p className="muted small">
          Shortlist vide : ajoutez des candidats depuis la recherche de talents.
        </p>
      ) : (
        sl.items.map((item) => (
          <div className="app-row" key={item.candidate_id}>
            <div className="app-head">
              <div>
                <strong>{item.name}</strong>
                {item.verified && (
                  <span className="verified-chip" style={{ marginLeft: "0.5rem" }}>Vérifié</span>
                )}
                <p className="small muted" style={{ margin: 0 }}>
                  Ajouté le {fmtDate(item.added_at)}
                </p>
              </div>
              <div className="actions-row" style={{ marginTop: 0 }}>
                <button
                  className="btn btn-outline btn-small"
                  onClick={() => navigate(`/recruteur/candidats/${item.candidate_id}`)}
                >
                  Voir la carte
                </button>
                <button className="btn btn-primary btn-small" onClick={() => contact(item.candidate_id)}>
                  Contacter
                </button>
                <button
                  className="btn btn-remove btn-small"
                  onClick={() => removeItem(item.candidate_id)}
                  disabled={busy}
                >
                  Retirer
                </button>
              </div>
            </div>
          </div>
        ))
      )}
      <div className="actions-row">
        <button className="btn btn-ghost btn-small" onClick={removeList} disabled={busy}>
          Supprimer la shortlist
        </button>
      </div>
    </section>
  );
}

export default function RecruiterShortlists() {
  const [lists, setLists] = useState(null);
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const reload = () => {
    api("/recruiter/shortlists").then(setLists).catch((e) => setError(e.detail));
  };

  useEffect(() => {
    reload();
  }, []);

  async function create(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError("");
    try {
      await api("/recruiter/shortlists", { method: "POST", body: { name: name.trim(), note } });
      setName("");
      setNote("");
      reload();
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  if (error && !lists) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!lists) {
    return <div className="page"><Loader /></div>;
  }

  return (
    <div className="page">
      <h1>Shortlists</h1>
      <p className="page-lead">
        Vos listes de candidats présélectionnés, privées à votre entreprise.
      </p>
      <ErrorNote error={error} />

      <form className="panel" onSubmit={create}>
        <h2>Créer une shortlist</h2>
        <div className="grid-2">
          <label className="field">
            <span>Nom de la liste *</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Ex. Shortlist techniciens réseau" />
          </label>
          <label className="field">
            <span>Note (poste visé, contexte…)</span>
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ex. Pour le poste de septembre" />
          </label>
        </div>
        <div className="actions-row">
          <button className="btn btn-primary" disabled={busy || !name.trim()}>
            {busy ? "…" : "Créer"}
          </button>
        </div>
      </form>

      {lists.length === 0 && (
        <Empty title="Aucune shortlist">
          <p>Créez une liste, puis ajoutez-y des candidats depuis la recherche de talents.</p>
        </Empty>
      )}
      {lists.map((sl) => (
        <ShortlistCard key={sl.id} sl={sl} onChanged={reload} />
      ))}
    </div>
  );
}
