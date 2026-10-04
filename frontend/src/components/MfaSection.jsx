import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { ErrorNote } from "./ui.jsx";
import { useAuth } from "../context/AuthContext.jsx";

// Section MFA partagée (Profil candidat + Paramètres de compte
// admin/recruteur). L'état AFFICHÉ se resynchronise toujours avec le
// serveur : à l'ouverture et après chaque activation/désactivation.
// Corrige le bug visuel « bouton Activer MFA alors qu'il est déjà actif ».

export default function MfaSection() {
  const { refreshUser } = useAuth();
  const [phase, setPhase] = useState("loading"); // loading | idle | setup | enabled
  const [setup, setSetup] = useState(null);
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // À l'ouverture : l'état réel du MFA vient du serveur, jamais d'une
  // copie locale périmée.
  useEffect(() => {
    let alive = true;
    api("/auth/me")
      .then((me) => {
        if (!alive) return;
        setPhase(me.mfa_enabled ? "enabled" : "idle");
      })
      .catch((e) => {
        if (alive) {
          setError(e.detail);
          setPhase("idle");
        }
      });
    return () => { alive = false; };
  }, []);

  async function startSetup() {
    setBusy(true);
    setError("");
    try {
      const res = await api("/auth/mfa/setup", { method: "POST" });
      setSetup(res);
      setPhase("setup");
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function enable(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api("/auth/mfa/enable", { method: "POST", body: { code } });
      setRecovery(res.recovery_codes);
      setCode("");
      setPhase("enabled");
      // Resynchronise l'utilisateur : mfa_enabled = true côté contexte
      await refreshUser();
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function disable(e) {
    e.preventDefault();
    const input = e.target.elements.code;
    setBusy(true);
    setError("");
    try {
      await api("/auth/mfa/disable", { method: "POST", body: { code: input.value } });
      setPhase("idle");
      setSetup(null);
      setRecovery(null);
      await refreshUser();
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel">
      <h2>Sécurité : double authentification (MFA)</h2>
      <p className="small muted">
        Protégez votre compte avec une application d'authentification
        (Google Authenticator, Authy…). En cas de perte, vos codes de
        récupération restent valables ; un administrateur peut aussi
        réinitialiser votre MFA en cas extrême.
      </p>
      <ErrorNote error={error} />

      {phase === "loading" && <p className="small muted">Vérification de l'état du compte…</p>}

      {phase === "idle" && (
        <button className="btn btn-primary" onClick={startSetup} disabled={busy}>
          {busy ? "…" : "Activer le MFA"}
        </button>
      )}

      {phase === "setup" && setup && (
        <form onSubmit={enable}>
          <div className="grid-2">
            <div>
              {setup.qr_data_url
                ? <img src={setup.qr_data_url} alt="QR code MFA" width="160" height="160" />
                : <p className="small muted">QR indisponible : saisissez le secret ci-contre.</p>}
              <p className="small muted">Scannez le QR code, OU saisissez le secret manuellement.</p>
            </div>
            <div>
              <label className="field">
                <span>Secret à saisir dans l'application</span>
                <input readOnly value={setup.secret} onFocus={(e) => e.target.select()} />
              </label>
              <button
                type="button"
                className="btn btn-ghost btn-small"
                onClick={() => navigator.clipboard?.writeText(setup.secret)}
              >
                Copier le secret
              </button>
            </div>
          </div>
          <label className="field">
            <span>Code à 6 chiffres généré par l'application</span>
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="000000" required />
          </label>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? "…" : "Activer"}
          </button>
        </form>
      )}

      {phase === "enabled" && (
        <form onSubmit={disable}>
          <div className="alert alert-success">MFA actif sur votre compte.</div>
          {recovery && (
            <div className="alert alert-info">
              <strong>Conservez ces codes de récupération</strong> (montrés une seule fois) :
              <ul className="explain-list">
                {recovery.map((c) => <li key={c}><code>{c}</code></li>)}
              </ul>
            </div>
          )}
          {!recovery && (
            <p className="small muted">
              Vos codes de récupération vous ont été affichés lors de
              l'activation. Un code = un accès de secours si vous perdez
              votre application.
            </p>
          )}
          <label className="field">
            <span>Pour désactiver le MFA, saisissez un code actuel</span>
            <input name="code" placeholder="000000 ou code de récupération" required />
          </label>
          <button className="btn btn-remove" disabled={busy}>
            {busy ? "…" : "Désactiver le MFA"}
          </button>
        </form>
      )}
    </div>
  );
}
