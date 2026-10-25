import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client.js";
import { fmtDateTime } from "../../lib.js";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";
import { Icon, I } from "../../components/icons.jsx";

// Sources & collecte multi-source (§50, V2) : connecteurs RSS/JSON,
// planification autonome par source, requêtes conditionnelles, fiabilité
// et import d'offre par URL (LinkedIn/JSON-LD → brouillon à valider).

const INTERVALS = [
  { value: 15, label: "Toutes les 15 minutes" },
  { value: 30, label: "Toutes les 30 minutes" },
  { value: 60, label: "Toutes les heures" },
  { value: 180, label: "Toutes les 3 heures" },
  { value: 360, label: "Toutes les 6 heures" },
  { value: 720, label: "Toutes les 12 heures" },
  { value: 1440, label: "Une fois par jour" },
];

function kindLabel(kind) {
  return kind === "rss" ? "Flux RSS / Atom" : "API JSON";
}

function healthOf(source) {
  if (!source.enabled) return { label: "Suspendue", tone: "is-off" };
  if (source.health === "error") return { label: "À vérifier", tone: "is-error" };
  if (source.health === "idle") return { label: "À tester", tone: "is-idle" };
  if (source.health === "warning") return { label: "Fragile", tone: "is-warn" };
  return { label: "Opérationnelle", tone: "is-ok" };
}

function nextRunLabel(source) {
  if (!source.enabled) return "Collecte automatique suspendue";
  if (source.is_due) return "Collecte due";
  if (!source.next_run_at) return "En attente de la première collecte";
  return `Prochaine collecte : ${fmtDateTime(source.next_run_at)}`;
}

function SourceForm({ onSaved, onNotice }) {
  const [form, setForm] = useState({
    name: "",
    kind: "rss",
    url: "",
    sector: "",
    interval_minutes: 60,
  });
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");
  const [test, setTest] = useState(null);
  const set = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  async function testSource() {
    setTesting(true);
    setError("");
    setTest(null);
    try {
      const result = await api("/admin/sources/test", {
        method: "POST",
        body: { kind: form.kind, url: form.url },
      });
      setTest(result);
    } catch (err) {
      setTest({ ok: false, detail: err.detail });
    } finally {
      setTesting(false);
    }
  }

  async function submit(event) {
    event.preventDefault();
    const sourceName = form.name.trim();
    if (!sourceName) {
      setError("Le nom de la source est obligatoire.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api("/admin/sources", {
        method: "POST",
        body: {
          ...form,
          name: sourceName,
          interval_minutes: Number(form.interval_minutes) || 60,
        },
      });
      setForm({
        name: "",
        kind: "rss",
        url: "",
        sector: "",
        interval_minutes: 60,
      });
      setTest(null);
      onNotice(`Source « ${sourceName} » ajoutée et planifiée.`);
      onSaved();
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="source-side-card" id="ajouter-source">
      <div className="source-side-head">
        <span className="source-side-icon">
          <Icon d={I.plus} size={18} />
        </span>
        <div>
          <h2>Ajouter une source</h2>
          <p>
            Un flux RSS ou une API JSON. La source est testée avant d'être
            planifiée.
          </p>
        </div>
      </div>
      <form onSubmit={submit}>
        <ErrorNote error={error} />
        <label className="field">
          <span>Nom de la source *</span>
          <input
            value={form.name}
            onChange={(event) => set("name", event.target.value)}
            required
            placeholder="Ex. Offres Emploi CM"
          />
        </label>
        <div className="grid-2">
          <label className="field">
            <span>Type</span>
            <select
              value={form.kind}
              onChange={(event) => set("kind", event.target.value)}
            >
              <option value="rss">Flux RSS / Atom</option>
              <option value="json">API JSON</option>
            </select>
          </label>
          <label className="field">
            <span>Fréquence</span>
            <select
              value={form.interval_minutes}
              onChange={(event) =>
                set("interval_minutes", Number(event.target.value))
              }
            >
              {INTERVALS.map((interval) => (
                <option key={interval.value} value={interval.value}>
                  {interval.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="field">
          <span>URL du flux / de l'API *</span>
          <input
            value={form.url}
            onChange={(event) => set("url", event.target.value)}
            required
            placeholder="https://…/feed.xml"
          />
        </label>
        <label className="field">
          <span>Secteur par défaut (si non détecté)</span>
          <input
            value={form.sector}
            onChange={(event) => set("sector", event.target.value)}
            placeholder="Ex. BTP / Construction"
          />
        </label>
        <div className="actions-row">
          <button
            type="button"
            className="btn btn-outline btn-small"
            onClick={testSource}
            disabled={testing || busy || !form.url}
          >
            {testing ? "Test en cours…" : "Tester le flux"}
          </button>
          <button className="btn btn-primary btn-small" disabled={busy}>
            {busy ? "Ajout…" : "Ajouter la source"}
          </button>
        </div>
        {test && (
          <div
            className={`source-test-result ${
              test.ok ? "is-ok" : "is-error"
            }`}
          >
            <strong>{test.ok ? "Flux lisible" : "Lecture impossible"}</strong>
            <span>{test.detail}</span>
            {test.sample?.title && (
              <span>Premier élément : {test.sample.title}</span>
            )}
          </div>
        )}
      </form>
    </section>
  );
}

function ImportUrlForm({ onDraft }) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState(null);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setDraft(null);
    try {
      const result = await api("/admin/import-url", {
        method: "POST",
        body: { url },
      });
      setDraft(result);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="source-side-card">
      <div className="source-side-head">
        <span className="source-side-icon source-side-icon-accent">
          <Icon d={I.link} size={18} />
        </span>
        <div>
          <h2>Importer une offre par URL</h2>
          <p>
            LinkedIn ou autre page publique : le balisage JSON-LD produit un
            brouillon à vérifier avant publication.
          </p>
        </div>
      </div>
      <form onSubmit={submit}>
        <ErrorNote error={error} />
        {draft && (
          <div className="alert alert-info">
            <div>
              Brouillon extrait : {draft.title || "titre à préciser"} ·{" "}
              {draft.company || "entreprise à préciser"} ·{" "}
              {draft.location || "lieu à préciser"}.
            </div>
            <button
              type="button"
              className="btn btn-outline btn-small"
              onClick={() => onDraft(draft)}
            >
              Vérifier dans le formulaire d'offre
            </button>
          </div>
        )}
        <label className="field">
          <span>URL de l'offre *</span>
          <input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            required
            placeholder="https://www.linkedin.com/jobs/view/…"
          />
        </label>
        <div className="actions-row">
          <button className="btn btn-primary btn-small" disabled={busy}>
            {busy ? "Analyse…" : "Extraire l'offre"}
          </button>
        </div>
        <p className="small muted">
          Une seule page fournie par l'utilisateur, jamais de collecte de
          masse. Le brouillon reste soumis à validation humaine.
        </p>
      </form>
    </section>
  );
}

function SourceCard({
  source,
  running,
  disabled,
  onRun,
  onReload,
  onNotice,
  onError,
}) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    name: source.name,
    kind: source.kind,
    url: source.url,
    sector: source.sector || "",
    interval_minutes: source.interval_minutes || 60,
  });

  useEffect(() => {
    if (!editing) {
      setForm({
        name: source.name,
        kind: source.kind,
        url: source.url,
        sector: source.sector || "",
        interval_minutes: source.interval_minutes || 60,
      });
    }
  }, [source, editing]);

  const health = healthOf(source);
  const reliability = source.reliability_pct;
  const meterWidth = reliability == null ? 0 : Math.max(0, Math.min(100, reliability));
  const set = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  async function saveEdit(event) {
    event.preventDefault();
    const sourceName = form.name.trim();
    if (!sourceName) {
      onError("Le nom de la source est obligatoire.");
      return;
    }
    setBusy(true);
    onError("");
    try {
      await api(`/admin/sources/${source.id}`, {
        method: "PUT",
        body: {
          ...form,
          name: sourceName,
          interval_minutes: Number(form.interval_minutes) || 60,
        },
      });
      setEditing(false);
      onNotice(`Source « ${source.name} » mise à jour.`);
      onReload();
    } catch (err) {
      onError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function toggle() {
    setBusy(true);
    onError("");
    try {
      await api(`/admin/sources/${source.id}`, {
        method: "PUT",
        body: { enabled: !source.enabled },
      });
      onNotice(
        source.enabled
          ? `Source « ${source.name} » suspendue.`
          : `Source « ${source.name} » réactivée.`
      );
      onReload();
    } catch (err) {
      onError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Supprimer la source « ${source.name} » ?`)) return;
    setBusy(true);
    onError("");
    try {
      await api(`/admin/sources/${source.id}`, { method: "DELETE" });
      onNotice(`Source « ${source.name} » supprimée.`);
      onReload();
    } catch (err) {
      onError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className={`source-card${source.enabled ? "" : " is-off"}`}>
      <div className="source-card-head">
        <div className="source-identity">
          <span
            className={`source-icon ${
              source.kind === "rss" ? "is-rss" : "is-json"
            }`}
          >
            <Icon
              d={source.kind === "rss" ? I.globe : I.database}
              size={19}
            />
          </span>
          <div className="source-identity-copy">
            <h3>{source.name}</h3>
            <p className="source-sub">
              {kindLabel(source.kind)} · {source.sector || "Tous secteurs"}
            </p>
            <p className="source-url">{source.url}</p>
          </div>
        </div>
        <div className="source-card-badges">
          <span className={`source-health ${health.tone}`}>{health.label}</span>
          <span
            className={`badge ${source.enabled ? "badge-strong" : "badge-none"}`}
          >
            {source.enabled ? "Automatique" : "Mode manuel"}
          </span>
        </div>
      </div>

      <div className="source-metrics">
        <div className="source-metric">
          <strong>{reliability == null ? "n/a" : `${reliability} %`}</strong>
          <span>Fiabilité</span>
        </div>
        <div className="source-metric">
          <strong>{source.offers_imported}</strong>
          <span>Offres importées</span>
        </div>
        <div className="source-metric">
          <strong>{source.offers_skipped}</strong>
          <span>Doublons évités</span>
        </div>
        <div className="source-metric">
          <strong>
            {source.runs > 0
              ? `${((source.last_duration_ms || 0) / 1000).toFixed(1)} s`
              : "n/a"}
          </strong>
          <span>Dernière durée</span>
        </div>
      </div>

      <div
        className="source-meter"
        role="img"
        aria-label={`Fiabilité ${reliability == null ? "non mesurée" : `${reliability} pour cent`}`}
      >
        <span style={{ width: `${meterWidth}%` }} />
      </div>

      <div className="source-status-line">
        <span>
          <Icon d={I.clock} size={14} />
          {source.last_run_at
            ? `Dernière collecte : ${fmtDateTime(source.last_run_at)}`
            : "Jamais collectée"}
        </span>
        <span>
          <Icon d={I.activity} size={14} />
          {nextRunLabel(source)}
        </span>
      </div>

      {source.last_error ? (
        <p className="source-error">Dernière erreur : {source.last_error}</p>
      ) : source.last_status ? (
        <p className="source-last-status">{source.last_status}</p>
      ) : null}

      <div className="source-actions">
        <button
          type="button"
          className="btn btn-primary btn-small"
          onClick={() => onRun(source)}
          disabled={disabled}
        >
          <Icon d={I.zap} size={15} />
          {running ? "Collecte en cours…" : "Collecter"}
        </button>
        <button
          type="button"
          className="btn btn-outline btn-small"
          onClick={() => setEditing((value) => !value)}
          disabled={busy || disabled}
        >
          <Icon d={I.pen} size={15} />
          {editing ? "Fermer" : "Modifier"}
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-small"
          onClick={toggle}
          disabled={busy || disabled}
        >
          {source.enabled ? "Suspendre" : "Activer"}
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-small source-delete"
          onClick={remove}
          disabled={busy || disabled}
        >
          Supprimer
        </button>
      </div>

      {editing && (
        <form className="source-edit" onSubmit={saveEdit}>
          <div className="grid-2">
            <label className="field">
              <span>Nom *</span>
              <input
                value={form.name}
                onChange={(event) => set("name", event.target.value)}
                required
              />
            </label>
            <label className="field">
              <span>Type</span>
              <select
                value={form.kind}
                onChange={(event) => set("kind", event.target.value)}
              >
                <option value="rss">Flux RSS / Atom</option>
                <option value="json">API JSON</option>
              </select>
            </label>
          </div>
          <label className="field">
            <span>URL *</span>
            <input
              value={form.url}
              onChange={(event) => set("url", event.target.value)}
              required
            />
          </label>
          <div className="grid-2">
            <label className="field">
              <span>Secteur par défaut</span>
              <input
                value={form.sector}
                onChange={(event) => set("sector", event.target.value)}
              />
            </label>
            <label className="field">
              <span>Fréquence</span>
              <select
                value={form.interval_minutes}
                onChange={(event) =>
                  set("interval_minutes", Number(event.target.value))
                }
              >
                {INTERVALS.map((interval) => (
                  <option key={interval.value} value={interval.value}>
                    {interval.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="actions-row">
            <button className="btn btn-primary btn-small" disabled={busy}>
              {busy ? "Enregistrement…" : "Enregistrer"}
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-small"
              onClick={() => setEditing(false)}
              disabled={busy}
            >
              Annuler
            </button>
          </div>
        </form>
      )}
    </article>
  );
}

export default function AdminSources() {
  const navigate = useNavigate();
  const [sources, setSources] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [runningId, setRunningId] = useState(null);
  const running = runningId !== null;

  const reload = useCallback(async () => {
    try {
      const data = await api("/admin/sources");
      setSources(data);
      setError("");
    } catch (err) {
      setError(err.detail);
    }
  }, []);

  useEffect(() => {
    reload();
    const timer = setInterval(() => {
      if (!document.hidden) reload();
    }, 60000);
    return () => clearInterval(timer);
  }, [reload]);

  const summary = useMemo(() => {
    if (!sources) return null;
    const active = sources.filter((source) => source.enabled).length;
    const imported = sources.reduce(
      (total, source) => total + (source.offers_imported || 0),
      0
    );
    const skipped = sources.reduce(
      (total, source) => total + (source.offers_skipped || 0),
      0
    );
    const rated = sources.filter(
      (source) => source.reliability_pct != null
    );
    const average = rated.length
      ? Math.round(
          rated.reduce(
            (total, source) => total + source.reliability_pct,
            0
          ) / rated.length
        )
      : null;
    const upcoming = sources
      .filter((source) => source.enabled && source.next_run_at)
      .sort(
        (left, right) =>
          new Date(left.next_run_at) - new Date(right.next_run_at)
      )[0];
    return { active, imported, skipped, average, upcoming };
  }, [sources]);

  if (error && !sources) {
    return (
      <div className="page">
        <ErrorNote error={error} />
      </div>
    );
  }
  if (!sources || !summary) {
    return (
      <div className="page">
        <Loader />
      </div>
    );
  }

  async function run(source) {
    setRunningId(source.id);
    setNotice("");
    setError("");
    try {
      const result = await api(`/admin/sources/${source.id}/run`, {
        method: "POST",
      });
      if (result.error) {
        setNotice(`Source « ${source.name} » : échec de collecte.`);
      } else if (result.not_modified) {
        setNotice(
          `Source « ${source.name} » : flux inchangé, aucun nouvel élément.`
        );
      } else {
        setNotice(
          `Source « ${source.name} » : ${result.imported} offre(s) importée(s), ` +
            `${result.skipped} doublon(s) ignoré(s).`
        );
      }
      await reload();
    } catch (err) {
      setError(err.detail);
    } finally {
      setRunningId(null);
    }
  }

  async function runAll() {
    setRunningId("all");
    setNotice("Collecte en cours sur les sources actives…");
    setError("");
    try {
      const results = await api("/admin/sources/run-all", {
        method: "POST",
      });
      const imported = results.reduce(
        (total, result) => total + (result.imported || 0),
        0
      );
      const skipped = results.reduce(
        (total, result) => total + (result.skipped || 0),
        0
      );
      const errors = results.filter((result) => result.error).length;
      setNotice(
        `Collecte terminée : ${imported} offre(s) importée(s), ` +
          `${skipped} doublon(s) ignoré(s)` +
          `${errors ? `, ${errors} source(s) en échec` : ""}.`
      );
      await reload();
    } catch (err) {
      setError(err.detail);
    } finally {
      setRunningId(null);
    }
  }

  return (
    <div className="page sources-page">
      <header className="sources-hero">
        <div className="sources-hero-copy">
          <span className="sources-kicker">
            <Icon d={I.layers} size={14} /> Collecte autonome
          </span>
          <h1>Sources & collecte</h1>
          <p>
            Les sources activées sont interrogées automatiquement à leur
            propre fréquence. Les téléchargements sont parallélisés, les flux
            inchangés ne sont pas reparsés et chaque offre conserve sa date
            de publication d'origine.
          </p>
          <div className="sources-hero-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={runAll}
              disabled={running || summary.active === 0}
            >
              <Icon d={I.zap} size={16} />
              {runningId === "all"
                ? "Collecte en cours…"
                : "Lancer les sources actives"}
            </button>
            <span className="sources-hero-note">
              <Icon d={I.clock} size={14} />
              {summary.upcoming
                ? summary.upcoming.is_due
                  ? "Une collecte est due"
                  : `Prochaine collecte : ${fmtDateTime(summary.upcoming.next_run_at)}`
                : "Aucune source active"}
            </span>
          </div>
        </div>
        <div className="sources-hero-badge">
          <span className="sources-hero-ring">
            <Icon d={I.activity} size={22} />
          </span>
          <strong>{summary.active}</strong>
          <span>source(s) en veille</span>
        </div>
      </header>

      {notice && <div className="alert alert-success">{notice}</div>}
      <ErrorNote error={error} />

      <div className="opps-stats sources-stats">
        <div className="opps-stat opps-stat-green">
          <span className="opps-stat-icon">
            <Icon d={I.layers} size={19} />
          </span>
          <div className="opps-stat-num">{summary.active}</div>
          <div className="opps-stat-label">Sources actives</div>
          <div className="opps-stat-note">
            sur {sources.length} configurée(s)
          </div>
        </div>
        <div className="opps-stat opps-stat-blue">
          <span className="opps-stat-icon">
            <Icon d={I.briefcase} size={19} />
          </span>
          <div className="opps-stat-num">{summary.imported}</div>
          <div className="opps-stat-label">Offres collectées</div>
          <div className="opps-stat-note">toutes sources confondues</div>
        </div>
        <div className="opps-stat opps-stat-violet">
          <span className="opps-stat-icon">
            <Icon d={I.filter} size={19} />
          </span>
          <div className="opps-stat-num">{summary.skipped}</div>
          <div className="opps-stat-label">Doublons évités</div>
          <div className="opps-stat-note">déduplication inter-sources</div>
        </div>
        <div className="opps-stat sources-stat-orange">
          <span className="opps-stat-icon">
            <Icon d={I.shield} size={19} />
          </span>
          <div className="opps-stat-num">
            {summary.average == null ? "n/a" : `${summary.average} %`}
          </div>
          <div className="opps-stat-label">Fiabilité moyenne</div>
          <div className="opps-stat-note">succès des dernières collectes</div>
        </div>
      </div>

      <div className="sources-layout">
        <section className="sources-main">
          <div className="sources-toolbar">
            <div>
              <h2>Vos connecteurs</h2>
              <p className="small muted">
                Activez, modifiez ou lancez une collecte à la demande. Les
                sources actives continuent de tourner en arrière-plan.
              </p>
            </div>
            <a className="btn btn-outline btn-small" href="#ajouter-source">
              <Icon d={I.plus} size={15} /> Ajouter une source
            </a>
          </div>

          {sources.length === 0 ? (
            <Empty title="Aucune source configurée">
              <p>
                Ajoutez un flux RSS ou une API JSON pour automatiser la
                collecte. La source sera testée, puis planifiée selon la
                fréquence choisie.
              </p>
              <a className="btn btn-primary" href="#ajouter-source">
                Configurer la première source
              </a>
            </Empty>
          ) : (
            sources.map((source) => (
              <SourceCard
                key={source.id}
                source={source}
                running={runningId === source.id}
                disabled={running}
                onRun={run}
                onReload={reload}
                onNotice={setNotice}
                onError={setError}
              />
            ))
          )}
        </section>

        <aside className="sources-side">
          <SourceForm onSaved={reload} onNotice={setNotice} />
          <ImportUrlForm
            onDraft={(draft) =>
              navigate("/admin/offres", { state: { draft } })
            }
          />
        </aside>
      </div>
    </div>
  );
}
