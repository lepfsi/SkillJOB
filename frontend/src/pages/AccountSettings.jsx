import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { ErrorNote } from "../components/ui.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import AgentPreferencesForm from "../components/AgentPreferencesForm.jsx";
import MfaSection from "../components/MfaSection.jsx";
import VerificationSection from "../components/VerificationSection.jsx";

// Paramètres de compte : MFA et notifications. Le catalogue d'événements
// est renvoyé par le backend selon le rôle (candidat, recruteur, admin).
const GROUP_LABELS = {
  offres: "Offres",
  candidatures: "Candidatures et entretiens",
  relations: "Messages",
  compte: "Compte",
  agent: "Agent carrière",
  administration: "Administration",
  technique: "Technique",
  autres: "Autres",
};

function NotificationsSection({ role }) {
  const [prefs, setPrefs] = useState(null);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState(null);
  const [telegramChats, setTelegramChats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    setBusy(true);
    api("/profile/notifications")
      .then((data) => {
        if (alive) setPrefs(data);
      })
      .catch((e) => {
        if (alive) setError(e.detail);
      })
      .finally(() => {
        if (alive) setBusy(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  // L'ancre #notifications peut être ouverte depuis un e-mail ou depuis
  // le lien « Configurer les canaux » de Mon agent.
  useEffect(() => {
    if (!prefs || window.location.hash !== "#notifications") return;
    const target = document.getElementById("notifications");
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [prefs]);

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { event_types, event_catalog, role: _role, ...payload } = prefs;
      const updated = await api("/profile/notifications", {
        method: "PUT",
        body: payload,
      });
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

  const set = (k, v) => setPrefs((p) => ({ ...p, [k]: v }));
  const isCandidate = (prefs?.role || role) === "candidate";
  const catalog =
    prefs?.event_catalog ||
    Object.entries(prefs?.event_types || {}).map(([key, label]) => ({
      key,
      label,
      description: "",
      group: "autres",
    }));
  const groups = {};
  for (const item of catalog) {
    const group = item.group || "autres";
    if (!groups[group]) groups[group] = [];
    groups[group].push(item);
  }

  return (
    <form className="panel" id="notifications" onSubmit={save}>
      <h2>Notifications e-mail</h2>
      <p className="small muted">
        Choisissez comment la plateforme vous prévient : par e-mail,
        WhatsApp ou Telegram, selon les informations que VOUS fournissez.
        Les services sont configurés par l'administrateur.
      </p>
      <ErrorNote error={error} />
      {!prefs ? (
        <p className="small muted">Chargement des préférences…</p>
      ) : (
        <>
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
                  Aucun chat détecté : ouvrez Telegram, démarrez une
                  conversation avec le bot OrientSkill et envoyez /start :
                  le bot affichera votre chat ID, et il apparaîtra ici.
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

          {isCandidate && (
            <div className="events-prefs">
              <h3>Fréquence des alertes emploi</h3>
              <p className="small muted">
                Les offres restent toujours visibles dans l'application.
                L'e-mail est plafonné à un envoi par jour pour éviter la
                surcharge.
              </p>
              <div className="grid-2">
                <label className="check">
                  <input
                    type="radio"
                    name="email_frequency"
                    value="daily"
                    disabled={!prefs.email_enabled}
                    checked={(prefs.email_frequency || "daily") === "daily"}
                    onChange={() => set("email_frequency", "daily")}
                  />
                  Résumé quotidien
                </label>
                <label className="check">
                  <input
                    type="radio"
                    name="email_frequency"
                    value="immediate"
                    disabled={!prefs.email_enabled}
                    checked={prefs.email_frequency === "immediate"}
                    onChange={() => set("email_frequency", "immediate")}
                  />
                  Immédiate (au plus un e-mail par jour)
                </label>
              </div>
            </div>
          )}

          {/* Choix PAR ÉVÉNEMENT : e-mail ou uniquement in-app */}
          <div className="events-prefs">
            <h3>
              {isCandidate
                ? "Catégories d'e-mails"
                : "Alertes qui vous concernent"}
            </h3>
            <p className="small muted">
              Pour chaque catégorie, cochez si vous voulez aussi la recevoir
              par e-mail. Non cochée, l'information reste disponible dans la
              section Notifications de l'application. L'e-mail requiert un
              canal E-mail activé avec votre adresse.
            </p>
            {!prefs.email_enabled && (
              <p className="small muted">
                Le canal E-mail est désactivé : activez-le ci-dessus pour
                recevoir ces catégories par e-mail.
              </p>
            )}
            {Object.entries(groups).map(([group, items]) => (
              <div className="events-group" key={group}>
                <h4>{GROUP_LABELS[group] || group}</h4>
                <div className="grid-2">
                  {items.map((item) => (
                    <label className="check" key={item.key}>
                      <input
                        type="checkbox"
                        disabled={!prefs.email_enabled}
                        checked={!!(prefs.events || {})[item.key]}
                        onChange={(e) =>
                          set("events", {
                            ...(prefs.events || {}),
                            [item.key]: e.target.checked,
                          })
                        }
                      />
                      <span>
                        <b>{item.label}</b>
                        {item.description && (
                          <>
                            <br />
                            <span className="small muted">
                              {item.description}
                            </span>
                          </>
                        )}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
            <p className="small muted">
              Les messages critiques de compte et de sécurité restent toujours
              envoyés, même si une catégorie est désactivée.
            </p>
          </div>
          <div className="actions-row">
            <button className="btn btn-primary" disabled={busy}>
              {busy ? "…" : "Enregistrer mes préférences"}
            </button>
            <button
              type="button"
              className="btn btn-outline"
              onClick={test}
              disabled={busy}
            >
              Tester l'envoi
            </button>
          </div>
          {results && (
            <div className="alert alert-info">
              {results.length === 0
                ? "Aucun canal activé : activez au moins un canal pour recevoir les notifications."
                : results.map((r) => (
                    <div key={r.channel}>
                      {r.channel === "email"
                        ? "E-mail"
                        : r.channel === "telegram"
                          ? "Telegram"
                          : "WhatsApp"}{" "}
                      : {r.ok ? "envoyé" : r.detail}
                    </div>
                  ))}
            </div>
          )}
        </>
      )}
    </form>
  );
}

export default function AccountSettings() {
  const { user } = useAuth();

  // Les liens « Gérer les paramètres » de Mon agent (#agent) et des
  // e-mails (#notifications) amènent directement au bon bloc.
  useEffect(() => {
    const id = window.location.hash.replace("#", "");
    if (!id) return;
    const target = document.getElementById(id);
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
      <NotificationsSection role={user?.role} />
    </div>
  );
}
