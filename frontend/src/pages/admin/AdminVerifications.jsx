import { useEffect, useState } from "react";
import { api, apiRaw } from "../../api/client.js";
import { fmtDateTime, VERIFICATION_LABELS } from "../../lib.js";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";

// File des vérifications : chaque demande montre la pièce ET le profil
// (nom, localisation, diplômes, certifications) pour COMPARER. Le refus
// exige un MOTIF, communiqué au candidat.

function RejectForm({ item, onDone, onCancel }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (note.trim().length < 5) {
      setError("Motif requis (au moins 5 caractères) : il sera communiqué au candidat.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(`/admin/verifications/${item.user_id}/reject`, {
        method: "POST",
        body: { note: note.trim() },
      });
      onDone();
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel-light" onSubmit={submit} style={{ marginTop: "0.6rem" }}>
      <h3>Motif du rejet (visible du candidat)</h3>
      <p className="small muted">
        Précisez la non-concordance constatée : nom différent du profil,
        pièce illisible, document expiré, photo non conforme…
      </p>
      <textarea
        rows="2"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Ex. Le nom sur la pièce (Jean Mbarga) ne correspond pas au nom du profil (Steve Demo)."
      />
      <ErrorNote error={error} />
      <div className="actions-row" style={{ marginTop: 0 }}>
        <button className="btn btn-remove btn-small" disabled={busy}>
          {busy ? "…" : "Confirmer le rejet"}
        </button>
        <button type="button" className="btn btn-ghost btn-small" onClick={onCancel}>
          Annuler
        </button>
      </div>
    </form>
  );
}

function VerificationCard({ item, onDecided }) {
  const [rejecting, setRejecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function approve() {
    setBusy(true);
    setError("");
    try {
      await api(`/admin/verifications/${item.user_id}/approve`, {
        method: "POST",
        body: { note: "Pièce conforme au profil." },
      });
      onDecided();
    } catch (err) {
      setError(err.detail);
      setBusy(false);
    }
  }

  async function viewDoc() {
    try {
      const res = await apiRaw(`/admin/verifications/${item.user_id}/document`);
      if (!res.ok) throw new Error("Document indisponible");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      setError(err.message);
    }
  }

  const pending = item.status === "pending";
  const profile = item.profile;

  return (
    <div className="app-row">
      <div className="app-head">
        <div>
          <strong>{item.full_name}</strong>
          <span className={`badge ${item.status === "verified" ? "badge-strong" : item.status === "pending" ? "badge-medium" : "badge-weak"}`} style={{ marginLeft: "0.5rem" }}>
            {VERIFICATION_LABELS[item.status] || item.status}
          </span>
          <p className="job-meta" style={{ margin: "0.15rem 0" }}>
            {item.email}
            {item.requested_at && ` · demande du ${fmtDateTime(item.requested_at)}`}
          </p>
          {item.note && <p className="small muted" style={{ margin: 0 }}>Note : {item.note}</p>}
        </div>
        <div className="actions-row" style={{ marginTop: 0 }}>
          <button className="btn btn-outline btn-small" onClick={viewDoc}>
            Examiner la pièce
          </button>
          {pending && (
            <>
              <button className="btn btn-primary btn-small" onClick={approve} disabled={busy}>
                Approuver
              </button>
              <button
                className="btn btn-remove btn-small"
                onClick={() => setRejecting((r) => !r)}
                disabled={busy}
              >
                Rejeter
              </button>
            </>
          )}
        </div>
      </div>

      {/* Comparaison : profil déclaré ↔ pièce déposée */}
      {pending && profile && (
        <div className="panel-light" style={{ marginTop: "0.5rem" }}>
          <h3 style={{ margin: 0 }}>Comparaison profil ↔ pièce</h3>
          <div className="grid-2">
            <div>
              <p className="small muted" style={{ margin: "0.2rem 0" }}>Profil déclaré</p>
              <p className="small" style={{ margin: 0 }}>
                Nom : {item.full_name}
                {profile.title && <> · Titre : {profile.title}</>}
                {(profile.location || profile.geo) && (
                  <> · Localisation : {profile.location || profile.geo}</>
                )}
                {profile.education && profile.education.length > 0 && (
                  <> · Diplôme(s) : {profile.education.filter(Boolean).join(", ")}</>
                )}
              </p>
            </div>
            <div>
              <p className="small muted" style={{ margin: "0.2rem 0" }}>À vérifier sur la pièce</p>
              <p className="small" style={{ margin: 0 }}>
                Nom complet identique · Photographie reconnaissable ·
                Document non expiré · Mention du nom de naissance si différent.
              </p>
            </div>
          </div>
        </div>
      )}

      {rejecting && pending && (
        <RejectForm
          item={item}
          onDone={() => { setRejecting(false); onDecided(); }}
          onCancel={() => setRejecting(false)}
        />
      )}
      <ErrorNote error={error} />
    </div>
  );
}

export default function AdminVerifications() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");

  const reload = () => {
    api("/admin/verifications").then(setItems).catch((e) => setError(e.detail));
  };

  useEffect(() => { reload(); }, []);

  if (error && !items) return <div className="page"><ErrorNote error={error} /></div>;
  if (!items) return <div className="page"><Loader /></div>;

  const pending = items.filter((i) => i.status === "pending");
  const decided = items.filter((i) => i.status !== "pending");

  return (
    <div className="page">
      <h1>Vérifications de profil</h1>
      <p className="page-lead">
        Comparez la pièce d'identité avec les informations du profil. Un
        refus exige un motif : il est communiqué au candidat pour qu'il
        puisse corriger sa demande.
      </p>

      <section className="section">
        <h2>En attente d'examen ({pending.length})</h2>
        {pending.length === 0 && (
          <Empty title="Aucune demande en attente">
            <p>Les nouvelles demandes de vérification apparaîtront ici.</p>
          </Empty>
        )}
        {pending.map((i) => <VerificationCard key={i.user_id} item={i} onDecided={reload} />)}
      </section>

      {decided.length > 0 && (
        <section className="section">
          <h2>Demandes traitées ({decided.length})</h2>
          {decided.map((i) => <VerificationCard key={i.user_id} item={i} onDecided={reload} />)}
        </section>
      )}
    </div>
  );
}
