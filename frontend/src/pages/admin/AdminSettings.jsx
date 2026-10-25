import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext.jsx";
import { api } from "../../api/client.js";
import { Loader, ErrorNote } from "../../components/ui.jsx";

// Paramètres des services : LLM, SMTP, réception des candidatures par
// e-mail, agrégateurs Telegram / WhatsApp. Les secrets soumis vides
// conservent la valeur existante ; ils ne sont jamais renvoyés par l'API
// (seulement « configuré »).

function TestResult({ test }) {
  if (!test) return null;
  return (
    <div
      className={`settings-test-result ${
        test.ok ? "is-ok" : "is-error"
      }`}
    >
      <strong>{test.ok ? "Test réussi" : "Test échoué"}</strong>
      <span>{test.detail}</span>
    </div>
  );
}

function LlmForm({ value, onSaved }) {
  const [form, setForm] = useState({
    provider: value.provider || "rules",
    model: value.model || "",
    base_url: value.base_url || "",
    api_key: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [test, setTest] = useState(null);
  const [testing, setTesting] = useState(false);
  const configured = value.api_key_set;

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = { ...form, enabled: form.provider === "openai" };
      if (!form.api_key) delete data.api_key;
      const res = await api("/admin/settings/llm", { method: "PUT", body: { data } });
      onSaved(res);
      setForm((f) => ({ ...f, api_key: "" }));
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function runTest() {
    setTesting(true);
    setError("");
    setTest(null);
    try {
      const res = await api("/admin/test-llm", { method: "POST" });
      setTest(res);
    } catch (err) {
      setTest({ ok: false, detail: err.detail });
    } finally {
      setTesting(false);
    }
  }

  return (
    <form className="panel" onSubmit={save}>
      <h2>Moteur IA (LLM)</h2>
      <p className="small muted">
        Sans clé, l'assistant fonctionne en moteur de règles local (données
        réelles, zéro invention). Avec une clé OpenAI-compatible, les réponses
        sont rédigées par le modèle. Secret actuel :{" "}
        <b>{configured ? "configuré" : "aucun"}</b>.
      </p>
      <div className="setting-grid">
        <label className="field">
          <span>Fournisseur</span>
          <select value={form.provider} onChange={(e) => set("provider", e.target.value)}>
            <option value="rules">Règles locales (sans LLM)</option>
            <option value="openai">API OpenAI-compatible</option>
          </select>
        </label>
        <label className="field">
          <span>Modèle</span>
          <input value={form.model} onChange={(e) => set("model", e.target.value)} placeholder="gpt-4o-mini" />
        </label>
        <label className="field">
          <span>URL de base</span>
          <input value={form.base_url} onChange={(e) => set("base_url", e.target.value)} placeholder="https://api.openai.com/v1" />
        </label>
        <label className="field">
          <span>Clé API {configured && "(laisser vide pour conserver l'actuelle)"}</span>
          <input type="password" value={form.api_key} onChange={(e) => set("api_key", e.target.value)} placeholder={configured ? "••••••••" : "sk-…"} />
        </label>
      </div>
      <div className="actions-row">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Enregistrement…" : "Enregistrer"}
        </button>
        <button type="button" className="btn btn-outline" onClick={runTest} disabled={testing}>
          {testing ? "Test en cours…" : "Tester la connexion"}
        </button>
      </div>
      <ErrorNote error={error} />
      <TestResult test={test} />
    </form>
  );
}

function SmtpForm({ value, onSaved }) {
  const [form, setForm] = useState({
    host: value.host || "",
    port: value.port || 587,
    username: value.username || "",
    password: "",
    from_email: value.from_email || "",
    use_tls: value.use_tls !== false,
    enabled: !!value.enabled,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [test, setTest] = useState(null);
  const [testing, setTesting] = useState(false);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = { ...form };
      if (!form.password) delete data.password;
      const res = await api("/admin/settings/smtp", { method: "PUT", body: { data } });
      onSaved(res);
      setForm((f) => ({ ...f, password: "" }));
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function runTest() {
    setTesting(true);
    setError("");
    setTest(null);
    try {
      const res = await api("/admin/test-smtp", { method: "POST" });
      setTest(res);
    } catch (err) {
      setTest({ ok: false, detail: err.detail });
    } finally {
      setTesting(false);
    }
  }

  return (
    <form className="panel" onSubmit={save}>
      <h2>Notifications e-mail (SMTP)</h2>
      <p className="small muted">
        Utilisé pour les alertes (nouvelles offres compatibles, relances de
        candidatures). Secret actuel : <b>{value.password_set ? "configuré" : "aucun"}</b>.
      </p>
      <div className="setting-grid">
        <label className="field">
          <span>Hôte SMTP</span>
          <input value={form.host} onChange={(e) => set("host", e.target.value)} placeholder="smtp.exemple.cm" />
        </label>
        <label className="field">
          <span>Port</span>
          <input type="number" value={form.port} onChange={(e) => set("port", Number(e.target.value))} />
        </label>
        <label className="field">
          <span>Utilisateur</span>
          <input value={form.username} onChange={(e) => set("username", e.target.value)} />
        </label>
        <label className="field">
          <span>Mot de passe {value.password_set && "(laisser vide pour conserver)"}</span>
          <input type="password" value={form.password} onChange={(e) => set("password", e.target.value)} />
        </label>
        <label className="field">
          <span>Adresse expéditrice</span>
          <input value={form.from_email} onChange={(e) => set("from_email", e.target.value)} placeholder="no-reply@orientskill.cm" />
        </label>
      </div>
      <div className="inline-fields">
        <label className="check">
          <input type="checkbox" checked={form.use_tls} onChange={(e) => set("use_tls", e.target.checked)} />
          Chiffrement TLS
        </label>
        <label className="check">
          <input type="checkbox" checked={form.enabled} onChange={(e) => set("enabled", e.target.checked)} />
          Activer le service
        </label>
      </div>
      <div className="actions-row">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Enregistrement…" : "Enregistrer"}
        </button>
        <button type="button" className="btn btn-outline" onClick={runTest} disabled={testing}>
          {testing ? "Test en cours…" : "Tester la connexion"}
        </button>
      </div>
      <ErrorNote error={error} />
      <TestResult test={test} />
    </form>
  );
}

function InboundForm({ value, onSaved }) {
  const [form, setForm] = useState({
    enabled: !!value.enabled,
    address: value.address || "",
    protocol: value.protocol || "imap",
    imap_host: value.imap_host || "",
    imap_port: value.imap_port || 993,
    imap_username: value.imap_username || "",
    imap_password: "",
    imap_use_ssl: value.imap_use_ssl !== false,
    imap_mailbox: value.imap_mailbox || "INBOX",
    poll_seconds: value.poll_seconds || 120,
    webhook_secret: "",
    fallback_email: value.fallback_email || "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [test, setTest] = useState(null);
  const [testing, setTesting] = useState(false);

  const set = (key, val) => setForm((f) => ({ ...f, [key]: val }));
  const webhookUrl = `${window.location.origin}/api/public/inbound-email`;

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = { ...form };
      if (!form.imap_password) delete data.imap_password;
      if (!form.webhook_secret) delete data.webhook_secret;
      const res = await api("/admin/settings/inbound", {
        method: "PUT",
        body: { data },
      });
      onSaved(res);
      setForm((f) => ({ ...f, imap_password: "", webhook_secret: "" }));
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function runTest() {
    setTesting(true);
    setError("");
    setTest(null);
    try {
      // Le test utilise les valeurs du formulaire courant, même avant
      // enregistrement. Un mot de passe vide réutilise le secret stocké.
      const data = {
        imap_host: form.imap_host,
        imap_port: Number(form.imap_port) || 993,
        imap_username: form.imap_username,
        imap_use_ssl: form.imap_use_ssl,
        imap_mailbox: form.imap_mailbox,
      };
      if (form.imap_password) data.imap_password = form.imap_password;
      const res = await api("/admin/test-imap", {
        method: "POST",
        body: { data },
      });
      setTest(res);
    } catch (err) {
      setTest({ ok: false, detail: err.detail });
    } finally {
      setTesting(false);
    }
  }

  function copyWebhook() {
    navigator.clipboard?.writeText(webhookUrl).catch(() => {});
  }

  return (
    <form className="panel" onSubmit={save}>
      <h2>Réception des candidatures par e-mail</h2>
      <p className="small muted">
        Adresse interne affichée sur le visuel public. Les candidatures sont
        routées par référence OS-XXXX, puis par mots-clés, puis par titre ou
        entreprise. Un compte candidat est créé si l'expéditeur n'en a pas, et
        ses accès lui sont envoyés. La transmission à l'entreprise joint les
        pièces d'origine.
      </p>
      <div className="setting-grid">
        <label className="field">
          <span>Adresse interne de réception</span>
          <input
            type="email"
            value={form.address}
            onChange={(e) => set("address", e.target.value)}
            placeholder="candidatures@orientskill.cm"
          />
          <span className="field-hint">
            Obligatoire pour générer le visuel public.
          </span>
        </label>
        <label className="field">
          <span>Adresse de secours (si l'offre n'a pas d'e-mail RH)</span>
          <input
            type="email"
            value={form.fallback_email}
            onChange={(e) => set("fallback_email", e.target.value)}
            placeholder="recrutement@orientskill.cm"
          />
        </label>
        <label className="field">
          <span>Mode de réception</span>
          <select value={form.protocol} onChange={(e) => set("protocol", e.target.value)}>
            <option value="imap">Relève IMAP de la boîte</option>
            <option value="webhook">Webhook du fournisseur</option>
          </select>
        </label>
        <label className="field">
          <span>Intervalle de relève (secondes)</span>
          <input
            type="number"
            min="30"
            value={form.poll_seconds}
            onChange={(e) => set("poll_seconds", Number(e.target.value))}
          />
        </label>
      </div>

      <div className="inbound-section">
        <h3>Boîte IMAP</h3>
        <div className="setting-grid">
          <label className="field">
            <span>Hôte IMAP</span>
            <input
              value={form.imap_host}
              onChange={(e) => set("imap_host", e.target.value)}
              placeholder="imap.gmail.com"
            />
          </label>
          <label className="field">
            <span>Port</span>
            <input
              type="number"
              value={form.imap_port}
              onChange={(e) => set("imap_port", Number(e.target.value))}
            />
          </label>
          <label className="field">
            <span>Utilisateur</span>
            <input
              value={form.imap_username}
              onChange={(e) => set("imap_username", e.target.value)}
              placeholder="candidatures@orientskill.cm"
            />
          </label>
          <label className="field">
            <span>Mot de passe {value.imap_password_set && "(laisser vide pour conserver)"}</span>
            <input
              type="password"
              value={form.imap_password}
              onChange={(e) => set("imap_password", e.target.value)}
              placeholder={value.imap_password_set ? "••••••••" : ""}
            />
          </label>
          <label className="field">
            <span>Dossier</span>
            <input
              value={form.imap_mailbox}
              onChange={(e) => set("imap_mailbox", e.target.value)}
              placeholder="INBOX"
            />
          </label>
        </div>
        <div className="inline-fields">
          <label className="check">
            <input
              type="checkbox"
              checked={form.imap_use_ssl}
              onChange={(e) => set("imap_use_ssl", e.target.checked)}
            />
            Connexion IMAP chiffrée (SSL/TLS)
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => set("enabled", e.target.checked)}
            />
            Activer la réception
          </label>
        </div>
        <div className="actions-row">
          <button type="button" className="btn btn-outline btn-small" onClick={runTest} disabled={testing}>
            {testing ? "Test en cours…" : "Tester la connexion IMAP"}
          </button>
        </div>
        <TestResult test={test} />
        <p className="small muted">
          Le test utilise les valeurs saisies ci-dessus, même avant
          enregistrement. Laissez le mot de passe vide pour réutiliser
          celui déjà configuré.
        </p>
      </div>

      <div className="inbound-section">
        <h3>Webhook fournisseur</h3>
        <p className="small muted">
          Pour un fournisseur qui pousse les messages (Mailgun, SendGrid ou
          passerelle interne). Le secret est vérifié à chaque appel.
        </p>
        <div className="inline-fields">
          <input readOnly value={webhookUrl} aria-label="URL du webhook" />
          <button type="button" className="btn btn-ghost btn-small" onClick={copyWebhook}>
            Copier l'URL
          </button>
        </div>
        <label className="field">
          <span>Secret du webhook {value.webhook_secret_set && "(configuré)"}</span>
          <input
            type="password"
            value={form.webhook_secret}
            onChange={(e) => set("webhook_secret", e.target.value)}
            placeholder={value.webhook_secret_set ? "••••••••" : "chaîne longue et aléatoire"}
          />
          <span className="field-hint">
            En-tête attendu : X-OrientSkill-Secret. Un jeton dans l'URL est aussi accepté.
          </span>
        </label>
      </div>

      <div className="actions-row">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Enregistrement…" : "Enregistrer"}
        </button>
      </div>
      <ErrorNote error={error} />
    </form>
  );
}

function AggregatorsForm({ value, onSaved }) {
  const [form, setForm] = useState({
    telegram: {
      bot_token: "",
      chat_id: value.telegram?.chat_id || "",
      enabled: !!value.telegram?.enabled,
    },
    whatsapp: {
      provider: value.whatsapp?.provider || "",
      api_key: "",
      phone_number_id: value.whatsapp?.phone_number_id || "",
      enabled: !!value.whatsapp?.enabled,
    },
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [telegramTest, setTelegramTest] = useState(null);

  const setChan = (chan, k, v) =>
    setForm((f) => ({ ...f, [chan]: { ...f[chan], [k]: v } }));

  async function testTelegram() {
    setTelegramTest(null);
    try {
      const res = await api("/admin/test-telegram", { method: "POST" });
      setTelegramTest(res);
    } catch (err) {
      setTelegramTest({ ok: false, detail: err.detail });
    }
  }

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = JSON.parse(JSON.stringify(form));
      if (!data.telegram.bot_token) delete data.telegram.bot_token;
      if (!data.whatsapp.api_key) delete data.whatsapp.api_key;
      const res = await api("/admin/settings/aggregators", { method: "PUT", body: { data } });
      onSaved(res);
      setForm((f) => ({
        ...f,
        telegram: { ...f.telegram, bot_token: "" },
        whatsapp: { ...f.whatsapp, api_key: "" },
      }));
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={save}>
      <h2>Agrégateurs Telegram / WhatsApp</h2>
      <p className="small muted">
        Canaux conversationnels et notifications (roadmap V2, §25bis). Les
        identifiants sont stockés ici pour préparer l'activation via les API
        officielles (Telegram Bot API, WhatsApp Business API).
      </p>
      <div className="grid-2">
        <div>
          <h3>Telegram</h3>
          <p className="small muted">
            Étapes : créez un bot avec <b>@BotFather</b> dans Telegram
            (/newbot), collez le token ci-dessous, activez le canal, puis
            cliquez « Tester le bot ». Dans Telegram, ouvrez ensuite une
            conversation avec votre bot et envoyez <b>/start</b> : il
            affichera le chat ID à copier dans les paramètres utilisateur.
          </p>
          <label className="field">
            <span>Bot token {value.telegram?.bot_token_set && "(configuré)"}</span>
            <input
              type="password"
              value={form.telegram.bot_token}
              onChange={(e) => setChan("telegram", "bot_token", e.target.value)}
              placeholder="123456:ABC-DEF…"
            />
          </label>
          <label className="field">
            <span>Chat ID de test (optionnel, canal d'essai admin)</span>
            <input value={form.telegram.chat_id} onChange={(e) => setChan("telegram", "chat_id", e.target.value)} />
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={form.telegram.enabled}
              onChange={(e) => setChan("telegram", "enabled", e.target.checked)}
            />
            Canal actif (bot + notifications)
          </label>
          <div className="actions-row" style={{ marginTop: "0.4rem" }}>
            <button type="button" className="btn btn-outline btn-small" onClick={testTelegram}>
              Tester le bot
            </button>
            {telegramTest && (
              <span className={`badge ${telegramTest.ok ? "badge-strong" : "badge-weak"}`}>
                {telegramTest.detail}
              </span>
            )}
          </div>
        </div>
        <div>
          <h3>WhatsApp Business</h3>
          <label className="field">
            <span>Agrégateur (Twilio, 360dialog…)</span>
            <input value={form.whatsapp.provider} onChange={(e) => setChan("whatsapp", "provider", e.target.value)} />
          </label>
          <label className="field">
            <span>Clé API {value.whatsapp?.api_key_set && "(configurée)"}</span>
            <input
              type="password"
              value={form.whatsapp.api_key}
              onChange={(e) => setChan("whatsapp", "api_key", e.target.value)}
            />
          </label>
          <label className="field">
            <span>Phone number ID</span>
            <input value={form.whatsapp.phone_number_id} onChange={(e) => setChan("whatsapp", "phone_number_id", e.target.value)} />
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={form.whatsapp.enabled}
              onChange={(e) => setChan("whatsapp", "enabled", e.target.checked)}
            />
            Prêt à activer
          </label>
        </div>
      </div>
      <div className="actions-row">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Enregistrement…" : "Enregistrer"}
        </button>
      </div>
      <ErrorNote error={error} />
    </form>
  );
}

function DigestForm({ value, onSaved }) {
  const [enabled, setEnabled] = useState(!!value.digest_enabled);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/admin/settings/notifications", {
        method: "PUT",
        body: { data: { digest_enabled: enabled } },
      });
      onSaved();
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={save}>
      <h2>Notifications intelligentes (digest)</h2>
      <p className="small muted">
        Chaque jour, chaque candidat ayant activé un canal reçoit UNIQUEMENT
        les nouvelles offres correspondant à son profil (score ≥ 45,
        publiées dans les dernières 24 h) : filtrage par pertinence pour
        éviter la surcharge informationnelle (§52).
      </p>
      <label className="check">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
        />
        Activer le digest quotidien
      </label>
      <div className="actions-row">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "…" : "Enregistrer"}
        </button>
      </div>
      <ErrorNote error={error} />
    </form>
  );
}

export default function AdminSettings() {
  const { user } = useAuth();
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api("/admin/settings").then(setSettings).catch((e) => setError(e.detail));
  }, []);

  if (user && user.role !== "admin") return <Navigate to="/" replace />;
  if (error) return <div className="page"><ErrorNote error={error} /></div>;
  if (!settings) return <div className="page"><Loader /></div>;

  const refresh = () => {
    setSaved(true);
    api("/admin/settings").then(setSettings);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="page">
      <h1>Paramètres des services</h1>
      <p className="page-lead">
        Les secrets ne sont jamais renvoyés en clair. Un champ secret laissé
        vide conserve la valeur existante.
      </p>
      {saved && <div className="alert alert-success">Paramètres enregistrés.</div>}
      <LlmForm value={settings.llm} onSaved={refresh} />
      <SmtpForm value={settings.smtp} onSaved={refresh} />
      <InboundForm value={settings.inbound || {}} onSaved={refresh} />
      <AggregatorsForm value={settings.aggregators} onSaved={refresh} />
      <DigestForm value={settings.notifications || {}} onSaved={refresh} />
    </div>
  );
}
