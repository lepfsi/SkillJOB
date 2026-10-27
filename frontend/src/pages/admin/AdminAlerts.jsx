import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { fmtDateTime } from "../../lib.js";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";

// Équipe d'administration et alertes : catégories activables,
// destinataires par catégorie et journal des alertes envoyées. Le bouton
// de test vérifie le routage sans envoyer le moindre e-mail.

function validEmail(email) {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test((email || "").trim());
}

function RecipientCard({
  recipient,
  categories,
  onChange,
  onRemove,
}) {
  function set(key, value) {
    onChange({ ...recipient, [key]: value });
  }

  function toggleCategory(key) {
    const active = recipient.categories.includes(key);
    set("categories", active
      ? recipient.categories.filter((item) => item !== key)
      : [...recipient.categories, key]);
  }

  const emailOk = validEmail(recipient.email);

  return (
    <div className={`panel admin-alert-recipient${emailOk ? "" : " is-invalid"}`}>
      <div className="grid-2">
        <label className="field">
          <span>Nom affiché</span>
          <input
            value={recipient.name}
            onChange={(e) => set("name", e.target.value)}
            placeholder="Ex. Cellule modération"
          />
        </label>
        <label className="field">
          <span>Adresse e-mail *</span>
          <input
            type="email"
            value={recipient.email}
            onChange={(e) => set("email", e.target.value)}
            placeholder="equipe@orientskill.cm"
          />
          {!emailOk && (
            <span className="field-hint">
              Adresse e-mail complète requise.
            </span>
          )}
        </label>
      </div>
      <div className="events-prefs">
        <h3>Catégories reçues</h3>
        {categories.map((category) => (
          <label className="check" key={category.key}>
            <input
              type="checkbox"
              checked={recipient.categories.includes(category.key)}
              onChange={() => toggleCategory(category.key)}
            />
            {category.label}
          </label>
        ))}
        <p className="small muted">
          Aucune case cochée : ce destinataire reçoit toutes les catégories.
        </p>
      </div>
      <button
        type="button"
        className="btn btn-remove btn-small"
        onClick={onRemove}
      >
        Retirer ce destinataire
      </button>
    </div>
  );
}

export default function AdminAlerts() {
  const [data, setData] = useState(null);
  const [config, setConfig] = useState(null);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [busy, setBusy] = useState(false);
  const [testBusy, setTestBusy] = useState(false);
  const [testCategory, setTestCategory] = useState("critical");
  const [testResult, setTestResult] = useState(null);

  useEffect(() => {
    api("/admin/alert-settings")
      .then((payload) => {
        setData(payload);
        setConfig(payload.config);
      })
      .catch((err) => setError(err.detail));
  }, []);

  if (error && !data) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!data || !config) {
    return <div className="page"><Loader /></div>;
  }

  function toggleGlobal(key) {
    setConfig((prev) => ({
      ...prev,
      categories: { ...prev.categories, [key]: !prev.categories[key] },
    }));
  }

  function updateRecipient(index, value) {
    setConfig((prev) => ({
      ...prev,
      recipients: prev.recipients.map((item, position) =>
        position === index ? value : item
      ),
    }));
  }

  function removeRecipient(index) {
    setConfig((prev) => ({
      ...prev,
      recipients: prev.recipients.filter((_, position) => position !== index),
    }));
  }

  function addRecipient() {
    setConfig((prev) => ({
      ...prev,
      recipients: [
        ...prev.recipients,
        { name: "", email: "", categories: ["critical"] },
      ],
    }));
  }

  async function save() {
    setBusy(true);
    setError("");
    setFlash("");
    const invalid = config.recipients.find((item) => !validEmail(item.email));
    if (invalid) {
      setError("Corrigez l'adresse e-mail invalide avant d'enregistrer.");
      setBusy(false);
      return;
    }
    try {
      const payload = await api("/admin/alert-settings", {
        method: "PUT",
        body: {
          enabled: !!config.enabled,
          categories: config.categories,
          recipients: config.recipients,
        },
      });
      setData(payload);
      setConfig(payload.config);
      setFlash("Équipe et catégories enregistrées.");
    } catch (err) {
      setError(err.detail || "Enregistrement impossible");
    } finally {
      setBusy(false);
    }
  }

  async function runTest() {
    setTestBusy(true);
    setError("");
    setTestResult(null);
    try {
      setTestResult(await api("/admin/alert-settings/test", {
        method: "POST",
        body: { category: testCategory },
      }));
    } catch (err) {
      setTestResult({
        ok: false,
        detail: err.detail || "Test impossible",
        recipients: [],
      });
    } finally {
      setTestBusy(false);
    }
  }

  return (
    <div className="page">
      <h1>Équipe d'administration et alertes</h1>
      <p className="page-lead">
        Choisissez les catégories d'alertes, les destinataires et consultez
        le journal des notifications envoyées. Les alertes critiques ont un
        repli sur les comptes administrateurs si aucun destinataire n'est
        configuré.
      </p>

      {flash && <div className="alert alert-success">{flash}</div>}
      <ErrorNote error={error} />

      <section className="panel">
        <div className="admin-alert-head">
          <div>
            <h2>Activation générale</h2>
            <p className="small muted">
              Les alertes utilisent le service SMTP configuré. Un service
              désactivé ne bloque pas la plateforme : chaque alerte reste
              journalisée ici.
            </p>
          </div>
          <label className="check">
            <input
              type="checkbox"
              checked={!!config.enabled}
              onChange={(e) =>
                setConfig((prev) => ({ ...prev, enabled: e.target.checked }))
              }
            />
            Alertes activées
          </label>
        </div>

        <div className="events-prefs">
          <h3>Catégories</h3>
          {data.categories.map((category) => (
            <label className="check" key={category.key}>
              <input
                type="checkbox"
                checked={!!config.categories[category.key]}
                onChange={() => toggleGlobal(category.key)}
              />
              {category.label}
              <span className="small muted admin-alert-desc">
                {category.description}
              </span>
            </label>
          ))}
        </div>

        {config.enabled && config.categories.critical && !(
          config.recipients.some((item) =>
            !item.categories.length || item.categories.includes("critical")
          )
        ) && (
          <div className="alert alert-error">
            Aucun destinataire ne reçoit les alertes critiques. Ajoutez-en un
            ou désactivez cette catégorie.
          </div>
        )}

        <h3>Destinataires</h3>
        {config.recipients.length === 0 ? (
          <p className="small muted">
            Aucun destinataire enregistré. Les alertes critiques sont envoyées
            aux comptes administrateurs par sécurité.
          </p>
        ) : (
          config.recipients.map((recipient, index) => (
            <RecipientCard
              key={`${recipient.email}-${index}`}
              recipient={recipient}
              categories={data.categories}
              onChange={(value) => updateRecipient(index, value)}
              onRemove={() => removeRecipient(index)}
            />
          ))
        )}
        <div className="actions-row">
          <button
            type="button"
            className="btn btn-outline btn-small"
            onClick={addRecipient}
          >
            Ajouter un destinataire
          </button>
          <button
            type="button"
            className="btn btn-primary btn-small"
            disabled={busy}
            onClick={save}
          >
            {busy ? "Enregistrement…" : "Enregistrer l'équipe"}
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="admin-alert-head">
          <div>
            <h2>Test de routage</h2>
            <p className="small muted">
              Vérifiez quels destinataires recevraient une catégorie. Aucun
              e-mail n'est envoyé.
            </p>
          </div>
          <div className="admin-alert-test">
            <select
              value={testCategory}
              onChange={(e) => setTestCategory(e.target.value)}
            >
              {data.categories.map((category) => (
                <option key={category.key} value={category.key}>
                  {category.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn btn-outline btn-small"
              disabled={testBusy}
              onClick={runTest}
            >
              {testBusy ? "Vérification…" : "Tester"}
            </button>
          </div>
        </div>
        {testResult && (
          <div
            className={`settings-test-result ${
              testResult.ok ? "is-ok" : "is-error"
            }`}
          >
            <strong>
              {testResult.ok ? "Routage opérationnel" : "Routage incomplet"}
            </strong>
            <span>
              {testResult.detail}
              {testResult.recipients?.length
                ? ` Destinataires : ${testResult.recipients.join(", ")}.`
                : ""}
            </span>
          </div>
        )}
      </section>

      <section className="panel">
        <h2>Journal des alertes</h2>
        <p className="small muted">
          Chaque alerte est conservée, même si le service e-mail est
          indisponible. Les adresses sont masquées dans la plateforme.
        </p>
        {data.journal.length === 0 ? (
          <Empty title="Aucune alerte pour le moment">
            <p>
              Les alertes de vérification, de recours, de signalement, de
              collecte et de défaillance critique apparaîtront ici.
            </p>
          </Empty>
        ) : (
          <div className="admin-alert-journal">
            {data.journal.map((row) => (
              <article className="admin-alert-row" key={row.id}>
                <div className="admin-alert-row-head">
                  <span className="chip">{row.category_label}</span>
                  <strong>{row.subject}</strong>
                  <span className="small muted">{fmtDateTime(row.created_at)}</span>
                </div>
                <p className="small muted admin-alert-recipients">
                  {row.recipients.length} destinataire(s) :{" "}
                  {row.recipients.join(", ") || "aucun"}
                </p>
                <p className="small">
                  {row.sent_count} envoi(s) réussi(s), {row.failed_count} échec(s).
                </p>
                {row.detail && (
                  <p className="small muted">{row.detail}</p>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
