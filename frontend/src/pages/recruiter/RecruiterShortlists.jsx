import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, resourceHref } from "../../api/client.js";
import { fmtDate, fmtDateTime } from "../../lib.js";
import ContactDialog from "../../components/ContactDialog.jsx";
import InterviewInviteDialog from "../../components/InterviewInviteDialog.jsx";
import VerifiedBadge from "../../components/VerifiedBadge.jsx";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";

// Shortlists (§20, V2) : listes de candidats présélectionnés par le
// recruteur, isolées entre entreprises.

const INVITE_LABELS = {
  pending: "Invitation en attente",
  accepted: "Créneau accepté",
  declined: "Autre créneau demandé",
};

function ShortlistCard({ sl, onChanged, invites, onInvitesChanged }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [contactTarget, setContactTarget] = useState(null);
  const [inviteTarget, setInviteTarget] = useState(null);

  const latestInvite = (candidateId) => (invites || [])
    .filter((row) => row.candidate_id === candidateId)
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];

  async function removeItem(candidateId) {
    setBusy(true);
    setError("");
    try {
      await api(`/recruiter/shortlists/${sl.id}/items/${candidateId}`, { method: "DELETE" });
      onChanged();
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function removeList() {
    if (!window.confirm(`Supprimer la shortlist « ${sl.name} » ?`)) return;
    setBusy(true);
    setError("");
    try {
      await api(`/recruiter/shortlists/${sl.id}`, { method: "DELETE" });
      onChanged();
    } catch (err) {
      setError(err.detail);
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
      <ErrorNote error={error} />
      {sl.items.length === 0 ? (
        <p className="muted small">
          Shortlist vide : ajoutez des candidats depuis la recherche de talents.
        </p>
      ) : (
        sl.items.map((item) => {
          const last = latestInvite(item.candidate_id);
          return (
            <div className="app-row" key={item.candidate_id}>
              <div className="app-head">
                <div>
                  <strong>{item.name}</strong>
                  {item.verified && (
                    <VerifiedBadge label="Vérifié" size={13} className="verified-inline" />
                  )}
                  <p className="small muted" style={{ margin: 0 }}>
                    Ajouté le {fmtDate(item.added_at)}
                  </p>
                  {last && (
                    <p className={`small invite-status invite-status-${last.status}`}>
                      {INVITE_LABELS[last.status]} · {fmtDateTime(last.slot_at)}
                      {last.status === "declined" && last.candidate_note
                        ? ` · « ${last.candidate_note} »`
                        : ""}
                    </p>
                  )}
                </div>
                <div className="actions-row" style={{ marginTop: 0 }}>
                  <button
                    className="btn btn-outline btn-small"
                    onClick={() => navigate(`/recruteur/candidats/${item.candidate_id}`)}
                  >
                    Voir la carte
                  </button>
                  <button
                    className="btn btn-outline btn-small"
                    onClick={() => setContactTarget({ user_id: item.candidate_id, full_name: item.name })}
                  >
                    Contacter
                  </button>
                  <button
                    className="btn btn-primary btn-small"
                    onClick={() => setInviteTarget({ user_id: item.candidate_id, full_name: item.name })}
                  >
                    Inviter en entretien
                  </button>
                  {last?.calendar_url && (
                    <a
                      className="btn btn-ghost btn-small"
                      href={resourceHref(last.calendar_url)}
                      title="Télécharger le créneau au format calendrier"
                    >
                      Calendrier (.ics)
                    </a>
                  )}
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
          );
        })
      )}
      <div className="actions-row">
        <button className="btn btn-ghost btn-small" onClick={removeList} disabled={busy}>
          Supprimer la shortlist
        </button>
      </div>
      {contactTarget && (
        <ContactDialog candidate={contactTarget} onClose={() => setContactTarget(null)} />
      )}
      {inviteTarget && (
        <InterviewInviteDialog
          candidate={inviteTarget}
          onClose={() => setInviteTarget(null)}
          onSent={() => onInvitesChanged?.()}
        />
      )}
    </section>
  );
}

export default function RecruiterShortlists() {
  const [lists, setLists] = useState(null);
  const [invites, setInvites] = useState([]);
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const reload = () => {
    api("/recruiter/shortlists").then(setLists).catch((e) => setError(e.detail));
  };

  const reloadInvites = () => {
    api("/recruiter/interviews")
      .then((rows) => setInvites(rows || []))
      .catch(() => setInvites([]));
  };

  useEffect(() => {
    reload();
    reloadInvites();
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
        <ShortlistCard
          key={sl.id}
          sl={sl}
          onChanged={reload}
          invites={invites}
          onInvitesChanged={reloadInvites}
        />
      ))}
    </div>
  );
}
