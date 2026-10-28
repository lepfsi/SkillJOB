import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { ErrorNote } from "../components/ui.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import AgentPreferencesForm from "../components/AgentPreferencesForm.jsx";
import MfaSection from "../components/MfaSection.jsx";
import VerificationSection from "../components/VerificationSection.jsx";

// Paramètres de compte pour administrateurs et recruteurs : MFA et
// notifications (ces rôles n'ont pas de profil candidat à construire).
function NotificationsSection() {
  const [prefs, setPrefs] = useState(null);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState(null);
  const [telegramChats, setTelegramChats] = useState(null);
  const [error, setError] = useState("");

  if (prefs === null && !busy) {
    setBusy(true);
    api("/profile/notifications")
      .then(setPrefs)
      .catch((e) => setError(e.detail))
      .finally(() => setBusy(false));
  }

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { event_types, ...payload } = prefs;
      const updated = await api("/profile/notifications", { method: "PUT", body: payload });
      setPrefs(updated);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function detectTelegramChats() {
    try {
      setTelegramChats(await api("/profile/telegram-chats"));
    } catch (err) {
      setError(err.detail);
    }
  }

  async function test() {
    setBusy(true);
    setResults(null);
    try {
      setResults(await api("/profile/notifications/test", { method: "POST" }));
    } finally {
      setBusy(false);
    }
  }

  if (!prefs) return null;
  const set = (k, v) => setPrefs((p) => ({ ...p, [k]: v }));

  return (
    <form className="panel" onSubmit={save}>
      <h2>Notifications</h2>
      <p className="small muted">
        Choisissez comment la plateforme vous prévient : par e-mail,
        WhatsApp ou Telegram, selon les informations que VOUS fournissez.
        Les services sont configurés par l'administrateur.
      </p>
      <ErrorNote error={error} />
      <div className="grid-2">
        <div>
          <label className="check">
            <input
              type="checkbox"
              checked={!!prefs.email_enabled}
              onChange={(e) => set("email_enabled", e.target.checked)}
            />
            E-mail
          </label>
          <label className="field">
            <span>Adresse e-mail de notification</span>
            <input
              type="email"
              value={prefs.email || ""}
              onChange={(e) => set("email", e.target.value)}
              placeholder="vous@exemple.cm"
            />
          </label>
        </div>
        <div>
          <label className="check">
            <input
              type="checkbox"
              checked={!!prefs.telegram_enabled}
              onChange={(e) => set("telegram_enabled", e.target.checked)}
            />
            Telegram
          </label>
          <label className="field">
            <span>Chat ID Telegram (nombre)</span>
            <input
              value={prefs.telegram_username || ""}
              onChange={(e) => set("telegram_username", e.target.value)}
              placeholder="Ex. 123456789"
            />
          </label>
          <button
            type="button"
            className="btn btn-ghost btn-small"
            onClick={detectTelegramChats}
          >
            Détecter mon chat ID
          </button>
          {telegramChats && telegramChats.length > 0 && (
            <div className="chip-row">
              {telegramChats.map((c) => (
                <button
                  key={c.chat_id}
                  type="button"
                  className="chip"
                  onClick={() => set("telegram_username", String(c.chat_id))}
                >
                  {c.name || c.username || "?"} · {c.chat_id}
                </button>
              ))}
            </div>
          )}
          {telegramChats && telegramChats.length === 0 && (
            <p className="small muted">
              Aucun chat détecté : ouvrez Telegram, démarrez une conversation
              avec le bot OrientSkill et envoyez /start : le bot affichera
              votre chat ID, et il apparaîtra ici.
            </p>
          )}
        </div>
      </div>
      <div>
        <label className="check">
          <input
            type="checkbox"
            checked={!!prefs.whatsapp_enabled}
            onChange={(e) => set("whatsapp_enabled", e.target.checked)}
          />
          WhatsApp Business (nécessite un gabarit approuvé, roadmap)
        </label>
        {prefs.whatsapp_enabled && (
          <label className="field">
            <span>Numéro WhatsApp</span>
            <input
              value={prefs.whatsapp_number || ""}
              onChange={(e) => set("whatsapp_number", e.target.value)}
              placeholder="+237 6XX XX XX XX"
            />
          </label>
        )}
      </div>

      {/* Choix PAR ÉVÉNEMENT : e-mail ou uniquement in-app */}
      <div className="events-prefs">
        <h3>Quand souhaitez-vous un e-mail ?</h3>
        <p className="small muted">
          Pour chaque événement, cochez si vous voulez aussi le recevoir par
          e-mail. Non coché, l'événement reste disponible dans la section
          Notifications de l'application. L'e-mail requiert un canal E-mail
          activé avec votre adresse.
        </p>
        {!prefs.email_enabled && (
          <p className="small muted">
            Le canal E-mail est désactivé : activez-le ci-dessus pour recevoir
            ces événements par e-mail.
          </p>
        )}
        <div className="grid-2">
          {Object.entries(prefs.event_types || {}).map(([key, label]) => (
            <label className="check" key={key}>
              <input
                type="checkbox"
                disabled={!prefs.email_enabled}
                checked={!!(prefs.events || {})[key]}
                onChange={(e) =>
                  set("events", { ...(prefs.events || {}), [key]: e.target.checked })
                }
              />
              {label}
            </label>
          ))}
        </div>
      </div>
      <div className="actions-row">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "…" : "Enregistrer mes préférences"}
        </button>
        <button type="button" className="btn btn-outline" onClick={test} disabled={busy}>
          Tester l'envoi
        </button>
      </div>
      {results && (
        <div className="alert alert-info">
          {results.length === 0
            ? "Aucun canal activé : activez au moins un canal pour recevoir les notifications."
            : results.map((r) => (
              <div key={r.channel}>
                {r.channel === "email" ? "E-mail" : r.channel === "telegram" ? "Telegram" : "WhatsApp"} :{" "}
                {r.ok ? "envoyé" : r.detail}
              </div>
            ))}
        </div>
      )}
    </form>
  );
}

export default function AccountSettings() {
  const { user } = useAuth();

  // Le lien « Gérer les paramètres » de Mon agent arrive avec #agent :
  // on amène directement le bloc de réglages, sans faire chercher.
  useEffect(() => {
    if (window.location.hash !== "#agent") return;
    const target = document.getElementById("agent");
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, []);

  return (
    <div className="page page-narrow">
      <h1>Paramètres</h1>
      <p className="page-lead">
        Sécurité de votre compte, canaux de notification
        {user?.role === "candidate"
          ? ", réglages de l'agent et vérification de profil"
          : ""}
        .
      </p>

      <section className="panel" id="agent">
        <h2>Agent carrière</h2>
        {user?.role === "candidate" ? (
          <AgentPreferencesForm theme="light" />
        ) : (
          <p className="small muted">
            Les réglages de l'agent carrière sont disponibles pour les comptes
            candidats. Votre espace {user?.role === "recruiter" ? "recruteur" : "administrateur"}{" "}
            ne comporte pas d'agent de candidature.
          </p>
        )}
      </section>

      {user?.role === "candidate" && <VerificationSection />}
      <MfaSection />
      <NotificationsSection />
    </div>
  );
}
