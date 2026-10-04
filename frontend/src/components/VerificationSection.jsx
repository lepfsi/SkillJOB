import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { VERIFICATION_LABELS } from "../lib.js";
import { ErrorNote } from "./ui.jsx";

// Vérification de profil « à notre manière » : dépôt d'une pièce
// d'identité (CNI/passeport) examinée par un administrateur, avec
// COMPARAISON profil ↔ pièce et refus motivé visible du candidat.
// Soumission en DEUX temps : sélection du fichier → APERÇU → confirmation
// explicite avant l'envoi.

export default function VerificationSection({ status, onStatusChange }) {
  const { user, refreshUser } = useAuth();
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  const current = status || user?.verification_status || "none";

  // Motif de refus communiqué par l'administrateur (comparaison pièce ↔ profil)
  useEffect(() => {
    api("/profile/verification")
      .then((v) => setNote(v.note || ""))
      .catch(() => {});
  }, [current]);

  async function confirm(e) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      await api("/profile/verification/request", { method: "POST", form });
      setFile(null);
      if (onStatusChange) onStatusChange("pending");
      await refreshUser();
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={confirm}>
      <h2>Vérification de profil</h2>
      <p className="small muted">
        Lutte contre les faux comptes, à notre manière : déposez une pièce
        d'identité (CNI ou passeport), un administrateur la compare à votre
        profil, et votre compte reçoit le badge « Profil vérifié », visible
        des recruteurs et intégré à vos CV. Le document est conservé
        uniquement le temps de l'examen.
      </p>
      <ErrorNote error={error} />

      {current === "verified" && (
        <div className="alert alert-success">
          Votre profil est vérifié : le badge rassure les recruteurs et
          apparaît sur vos CV.
        </div>
      )}
      {current === "pending" && (
        <div className="alert alert-info">
          Demande en cours d'examen par un administrateur. Réponse habituelle
          : sous 48 heures.
        </div>
      )}
      {current === "rejected" && (
        <div className="alert alert-error">
          <strong>Demande refusée.</strong>
          {note && (
            <p className="small" style={{ margin: "0.3rem 0" }}>
              Motif de l'administrateur : « {note} »
            </p>
          )}
          Déposez une nouvelle pièce lisible (recto, informations complètes,
          nom conforme au profil).
        </div>
      )}

      {(current === "none" || current === "rejected") && (
        <>
          <label className="btn btn-outline" style={{ cursor: "pointer", display: "inline-block" }}>
            Choisir ma pièce d'identité (JPG, PNG, WebP · 5 Mo max)
            <input
              type="file"
              accept=".jpg,.jpeg,.png,.webp"
              style={{ display: "none" }}
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </label>

          {file && (
            <div className="panel-light" style={{ marginTop: "0.6rem" }}>
              <h3 style={{ margin: 0 }}>À confirmer avant l'envoi</h3>
              <p className="small">
                Fichier sélectionné : <strong>{file.name}</strong>
                {" "}({Math.max(1, Math.round(file.size / 1024))} Ko)
              </p>
              <p className="small muted">
                Vérifiez : la pièce est lisible, le nom correspond à votre
                nom de profil, et le document n'est pas expiré. Une pièce non
                concordante sera refusée avec motif.
              </p>
              <div className="actions-row" style={{ marginTop: 0 }}>
                <button className="btn btn-primary" disabled={busy}>
                  {busy ? "Envoi…" : "Confirmer et envoyer pour vérification"}
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => setFile(null)}
                  disabled={busy}
                >
                  Annuler
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </form>
  );
}
