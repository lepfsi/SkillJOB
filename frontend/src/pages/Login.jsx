import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { api, setSession } from "../api/client.js";

// Écran de connexion : fond en couches (dégradé profond + halos doux +
// trame discrète), citation inspirante qui se renouvelle, carte épurée.

const QUOTES = [
  {
    text: "Ton parcours n'est pas un CV, c'est une histoire de compétences.",
    author: "OrientSkill AI",
  },
  {
    text: "Chaque petit boulot t'a appris quelque chose qu'un emploi recherchera demain.",
    author: "OrientSkill AI",
  },
  {
    text: "Comprendre le marché, c'est déjà prendre une longueur d'avance.",
    author: "OrientSkill AI",
  },
  {
    text: "L'absence de diplôme n'est pas l'absence de compétence.",
    author: "OrientSkill AI",
  },
  {
    text: "Le bon déclic, c'est la bonne compétence au bon moment.",
    author: "OrientSkill AI",
  },
];

function Quote() {
  const [index, setIndex] = useState(
    () => Math.floor(Math.random() * QUOTES.length)
  );
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setInterval(() => {
      setVisible(false);
      setTimeout(() => {
        setIndex((i) => (i + 1) % QUOTES.length);
        setVisible(true);
      }, 600);
    }, 7000);
    return () => clearInterval(timer);
  }, []);

  const quote = QUOTES[index];
  return (
    <blockquote
      className="auth-quote"
      style={{ opacity: visible ? 1 : 0, transition: "opacity 0.6s ease" }}
    >
      <p>{quote.text}</p>
      <cite>{quote.author}</cite>
    </blockquote>
  );
}

export default function Login() {
  const { login } = useAuth();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Recours : quand le compte est suspendu, la personne peut contester
  // sans perdre ses données (le compte reste intact).
  const [banned, setBanned] = useState(false);
  const [appeal, setAppeal] = useState("");
  const [appealBusy, setAppealBusy] = useState(false);
  const [appealDone, setAppealDone] = useState("");
  const [appealError, setAppealError] = useState("");

  // Étape 2 (MFA)
  const [mfaToken, setMfaToken] = useState(null);
  const [code, setCode] = useState("");

  async function finishLogin(token, user) {
    setSession(token, user);
    // Retour au lien profond (invitation à un entretien, par exemple),
    // uniquement pour un candidat et vers un chemin interne.
    const next = params.get("next") || "";
    const safeNext = next.startsWith("/") && !next.startsWith("//") ? next : "";
    if (user.role === "candidate" && safeNext) {
      window.location.href = safeNext;
      return;
    }
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
        await login(email.trim(), password).catch(() => {});
        finishLogin(res.token, res.user);
      }
    } catch (err) {
      const detail = err.detail || "Connexion impossible";
      setError(detail);
      if (/suspendu/i.test(detail)) setBanned(true);
    } finally {
      setBusy(false);
    }
  }

  async function submitAppeal() {
    setAppealBusy(true);
    setAppealError("");
    setAppealDone("");
    try {
      const row = await api("/auth/appeal", {
        method: "POST",
        body: {
          email: email.trim(),
          password,
          message: appeal.trim(),
        },
      });
      setAppealDone(
        row.status === "pending"
          ? "Votre recours est enregistré. L'administration l'examine ; votre compte et vos données restent intacts en attendant."
          : "Votre recours a été pris en compte."
      );
      setAppeal("");
    } catch (err) {
      setAppealError(err.detail || "Envoi impossible");
    } finally {
      setAppealBusy(false);
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
        <div className="auth-decor" aria-hidden="true" />
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
      <div className="auth-decor" aria-hidden="true" />
      <div className="auth-hero">
        <Quote />
      </div>
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

        {banned && (
          <section className="auth-appeal">
            <h2>Contester la suspension</h2>
            {appealDone ? (
              <div className="alert alert-success">{appealDone}</div>
            ) : (
              <>
                <p>
                  Votre compte et vos données restent enregistrés. Expliquez
                  votre situation ou répondez à une demande de complément :
                  l'administration examinera votre recours.
                </p>
                {appealError && <div className="alert alert-error">{appealError}</div>}
                <label className="field">
                  <span>Votre explication (20 caractères minimum)</span>
                  <textarea
                    rows={4}
                    minLength={20}
                    maxLength={2000}
                    value={appeal}
                    onChange={(e) => setAppeal(e.target.value)}
                    placeholder="Expliquez ce qui s'est passé et pourquoi votre compte devrait être réactivé."
                  />
                </label>
                <button
                  type="button"
                  className="btn btn-outline btn-block"
                  disabled={appealBusy || appeal.trim().length < 20}
                  onClick={submitAppeal}
                >
                  {appealBusy ? "Envoi…" : "Envoyer mon recours"}
                </button>
              </>
            )}
          </section>
        )}

        <p className="auth-alt">
          Pas encore de compte ? <Link to="/register">Créer un compte</Link>
        </p>
      </form>
    </div>
  );
}
