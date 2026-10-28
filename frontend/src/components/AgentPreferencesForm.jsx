import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { mapInternalPath } from "../lib.js";
import { ArrowIcon, Icon, I } from "./icons.jsx";
import { ErrorNote } from "./ui.jsx";

// Réglages de l'agent : un seul formulaire réutilisé dans « Mon agent »
// et dans les paramètres du compte (ancre #agent). Les actions cochées
// ici sont réellement appliquées par le backend, pas seulement masquées.

const MODE_ICONS = {
  accompagnement: I.shield,
  preparation: I.bot,
  veille: I.search,
  autonome: I.spark,
};

export default function AgentPreferencesForm({
  initial = null,
  onLoaded = null,
  onSaved = null,
  theme = "dark",
}) {
  const [data, setData] = useState(initial);
  const [draft, setDraft] = useState(initial ? initial.prefs : null);
  const [mode, setMode] = useState(initial ? initial.mode : "");
  const [loading, setLoading] = useState(!initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (initial) {
      setData(initial);
      setDraft(initial.prefs);
      setMode(initial.mode);
      setLoading(false);
      return undefined;
    }
    let alive = true;
    setLoading(true);
    api("/agent/preferences")
      .then((res) => {
        if (!alive) return;
        setData(res);
        setDraft(res.prefs);
        setMode(res.mode);
        if (onLoaded) onLoaded(res);
      })
      .catch((err) => {
        if (alive) setError(err.detail);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [initial]);

  // La page « Mon agent » peut recevoir les réglages après son premier
  // rendu : on resynchronise sans perdre la saisie en cours.
  useEffect(() => {
    if (!initial) return;
    setData(initial);
    setDraft(initial.prefs);
    setMode(initial.mode);
    setLoading(false);
  }, [initial]);

  if (loading) {
    return <p className="small muted">Chargement des réglages de l'agent…</p>;
  }
  if (!data || !draft) {
    return <ErrorNote error={error || "Réglages de l'agent indisponibles."} />;
  }

  const selectedScope =
    data.scopes.find((item) => item.id === draft.scope) || data.scopes[0];
  const selectedFrequency =
    data.frequencies.find((item) => item.id === draft.frequency) ||
    data.frequencies[0];
  const selectedValidation =
    data.validations.find((item) => item.id === draft.validation) ||
    data.validations[0];
  const modeConflict =
    mode === "autonome" && draft.validation === "toujours";

  function setField(key, value) {
    setNotice("");
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function toggleAction(actionId) {
    setNotice("");
    setDraft((current) => ({
      ...current,
      actions: {
        ...current.actions,
        [actionId]: !current.actions[actionId],
      },
    }));
  }

  async function save(event) {
    event.preventDefault();
    if (modeConflict) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updated = await api("/agent/preferences", {
        method: "PUT",
        body: {
          mode,
          scope: draft.scope,
          frequency: draft.frequency,
          validation: draft.validation,
          actions: draft.actions,
        },
      });
      setData(updated);
      setDraft(updated.prefs);
      setMode(updated.mode);
      setNotice("Réglages enregistrés. L'agent les applique dès maintenant.");
      if (onSaved) onSaved(updated);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className={`agent-prefs ${
        theme === "light" ? "agent-prefs-light" : "agent-prefs-dark"
      }`}
      onSubmit={save}
    >
      <p className="small muted agent-prefs-lead">
        Ces réglages sont enregistrés sur votre compte et appliqués par
        l'agent. Votre validation reste obligatoire avant tout envoi.
      </p>
      <ErrorNote error={error} />
      {notice && <div className="alert alert-success small">{notice}</div>}

      <fieldset className="agent-prefs-group">
        <legend>Mode de travail</legend>
        {data.modes.map((item) => {
          const disabled =
            item.id === "autonome" && draft.validation === "toujours";
          return (
            <button
              key={item.id}
              type="button"
              className={`ag-mode-opt ag-mode-button${
                item.id === mode ? " active" : ""
              }`}
              onClick={() => {
                setNotice("");
                setMode(item.id);
              }}
              disabled={busy || disabled}
              aria-pressed={item.id === mode}
            >
              <span className="ag-mode-opt-icon">
                <Icon d={MODE_ICONS[item.id] || I.bot} size={15} />
              </span>
              <span className="ag-mode-opt-main">
                <span className="ag-mode-opt-label">{item.label}</span>
                <span className="ag-mode-opt-desc">
                  {item.description || item.desc}
                </span>
              </span>
              {item.id === mode && (
                <span className="ag-mode-check">
                  <Icon d={I.check} size={14} />
                </span>
              )}
            </button>
          );
        })}
        {draft.validation === "toujours" && (
          <p className="small muted">
            Le mode autonome est indisponible avec une validation à chaque
            étape. Choisissez « Validation par document » pour l'activer.
          </p>
        )}
      </fieldset>

      <div className="agent-prefs-grid">
        <label className="field">
          <span>Périmètre d'action</span>
          <select
            value={draft.scope}
            onChange={(event) => setField("scope", event.target.value)}
            disabled={busy}
          >
            {data.scopes.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
          <span className="small muted">{selectedScope.description}</span>
        </label>
        <label className="field">
          <span>Fréquence de veille</span>
          <select
            value={draft.frequency}
            onChange={(event) => setField("frequency", event.target.value)}
            disabled={busy}
          >
            {data.frequencies.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
          <span className="small muted">{selectedFrequency.description}</span>
        </label>
        <label className="field">
          <span>Validation humaine</span>
          <select
            value={draft.validation}
            onChange={(event) => setField("validation", event.target.value)}
            disabled={busy}
          >
            {data.validations.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
          <span className="small muted">{selectedValidation.description}</span>
        </label>
      </div>

      <fieldset className="agent-prefs-group">
        <legend>Actions autorisées</legend>
        <p className="small muted">
          Décochez une action pour l'interdire à l'agent. Une action
          désactivée est bloquée côté serveur, pas seulement masquée.
        </p>
        <div className="grid-2">
          {data.actions.map((action) => (
            <label className="check" key={action.id}>
              <input
                type="checkbox"
                checked={!!draft.actions[action.id]}
                onChange={() => toggleAction(action.id)}
                disabled={busy}
              />
              <span>
                <b>{action.label}</b>
                <br />
                <span className="small muted">{action.description}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="agent-prefs-channels">
        <span>
          <Icon d={I.bell} size={14} /> Canaux d'alerte :{" "}
          <b>{data.channels.join(", ")}</b>
        </span>
        <Link className="link-more" to={mapInternalPath(data.channels_href)}>
          Configurer les canaux <ArrowIcon direction="right" size={12} />
        </Link>
      </div>

      <div className="actions-row">
        <button
          className="btn btn-primary"
          disabled={busy || modeConflict}
        >
          {busy ? "Enregistrement…" : "Enregistrer les réglages"}
        </button>
        {modeConflict && (
          <span className="small muted">
            Choisissez un autre mode ou une validation par document.
          </span>
        )}
      </div>
    </form>
  );
}
