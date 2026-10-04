import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext.jsx";
import { api } from "../../api/client.js";
import { Loader, ErrorNote } from "../../components/ui.jsx";

// Paramètres des services : LLM, SMTP, agrégateurs Telegram / WhatsApp.
// Les secrets soumis vides conservent la valeur existante ; ils ne sont
// jamais renvoyés par l'API (seulement « configuré »).

function LlmForm({ value, onSaved }) {
  const [form, setForm] = useState({
    provider: value.provider || "rules",
    model: value.model || "",
    base_url: value.base_url || "",
    api_key: "",
  });
  const [busy, setBusy] = useState(false);
  const [test, setTest] = useState(null);
  const configured = value.api_key_set;

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const data = { ...form, enabled: form.provider === "openai" };
      if (!form.api_key) delete data.api_key;
      const res = await api("/admin/settings/llm", { method: "PUT", body: { data } });
      onSaved(res);
      setForm((f) => ({ ...f, api_key: "" }));
    } finally {
      setBusy(false);
    }
  }

  async function runTest() {
    setTest("…");
    const res = await api("/admin/test-llm", { method: "POST" });
    setTest(res.detail);
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
        <button type="button" className="btn btn-outline" onClick={runTest}>
          Tester la connexion
        </button>
      </div>
      {test && <p className="small muted">{test}</p>}
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
  const [test, setTest] = useState(null);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const data = { ...form };
      if (!form.password) delete data.password;
      const res = await api("/admin/settings/smtp", { method: "PUT", body: { data } });
      onSaved(res);
      setForm((f) => ({ ...f, password: "" }));
    } finally {
      setBusy(false);
    }
  }

  async function runTest() {
    setTest("…");
    const res = await api("/admin/test-smtp", { method: "POST" });
    setTest(res.detail);
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
        <button type="button" className="btn btn-outline" onClick={runTest}>
          Tester la connexion
        </button>
      </div>
      {test && <p className="small muted">{test}</p>}
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
    </form>
  );
}

function DigestForm({ value, onSaved }) {
  const [enabled, setEnabled] = useState(!!value.digest_enabled);
  const [busy, setBusy] = useState(false);

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/admin/settings/notifications", {
        method: "PUT",
        body: { data: { digest_enabled: enabled } },
      });
      onSaved();
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
      <AggregatorsForm value={settings.aggregators} onSaved={refresh} />
      <DigestForm value={settings.notifications || {}} onSaved={refresh} />
    </div>
  );
}
