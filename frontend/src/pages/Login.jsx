import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { api, setSession } from "../api/client.js";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Étape 2 (MFA)
  const [mfaToken, setMfaToken] = useState(null);
  const [code, setCode] = useState("");

  async function finishLogin(token, user) {
    setSession(token, user);
    // Cloisonnement des rôles : chacun rejoint SON espace
    window.location.href =
      user.role === "admin" ? "/admin"
        : user.role === "recruiter" ? "/recruteur"
          : "/";
  }

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api("/auth/login", {
        method: "POST",
        body: { email: email.trim(), password },
      });
      if (res.mfa_required) {
        setMfaToken(res.mfa_token);
      } else {
        // Rafraîchit l'utilisateur côté contexte puis redirige
        await login(email.trim(), password).catch(() => {});
        finishLogin(res.token, res.user);
      }
    } catch (err) {
      setError(err.detail || "Connexion impossible");
    } finally {
      setBusy(false);
    }
  }

  async function onMfaSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api("/auth/login/mfa", {
        method: "POST",
        body: { mfa_token: mfaToken, code: code.trim() },
      });
      finishLogin(res.token, res.user);
    } catch (err) {
      setError(err.detail || "Code incorrect");
    } finally {
      setBusy(false);
    }
  }

  if (mfaToken) {
    return (
      <div className="auth-screen">
        <form className="auth-card" onSubmit={onMfaSubmit}>
          <div className="auth-brand">
            OrientSkill <span>AI</span>
          </div>
          <p className="auth-tagline">
            Votre compte est protégé par une double authentification. Saisissez
            le code de votre application d'authentification, ou un code de
            récupération.
          </p>
          {error && <div className="alert alert-error">{error}</div>}
          <label className="field">
            <span>Code à 6 chiffres ou code de récupération</span>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              required
              placeholder="000000"
              autoFocus
            />
          </label>
          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? "Vérification…" : "Valider"}
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="auth-screen">
      <form className="auth-card" onSubmit={onSubmit}>
        <div className="auth-brand">
          OrientSkill <span>AI</span>
        </div>
        <p className="auth-tagline">
          Se connaître. Comprendre le marché. Saisir les bonnes opportunités.
        </p>
        {error && <div className="alert alert-error">{error}</div>}
        <label className="field">
          <span>Adresse e-mail</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="vous@exemple.cm"
            autoComplete="email"
          />
        </label>
        <label className="field">
          <span>Mot de passe</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            placeholder="Votre mot de passe"
            autoComplete="current-password"
          />
        </label>
        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? "Connexion…" : "Se connecter"}
        </button>
        <p className="auth-alt">
          Pas encore de compte ? <Link to="/register">Créer un compte</Link>
        </p>
        <p className="auth-demo">
          Comptes de démonstration : demo@orientskill.cm / demo1234 ·
          admin@orientskill.cm / admin1234
        </p>
      </form>
    </div>
  );
}
