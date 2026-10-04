import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { fmtDateTime } from "../../lib.js";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";

// Sources & collecte multi-source (§50, V2) : connecteurs RSS/JSON,
// exécution manuelle, fiabilité par source, import d'offre par URL
// (LinkedIn/JSON-LD → brouillon à valider).

function AddSourceForm({ onSaved }) {
  const [form, setForm] = useState({ name: "", kind: "rss", url: "", sector: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/admin/sources", { method: "POST", body: form });
      setForm({ name: "", kind: "rss", url: "", sector: "" });
      onSaved();
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={submit}>
      <h2>Ajouter un connecteur</h2>
      <p className="small muted">
        Flux RSS d'un site d'offres, ou API JSON publique. Chaque source est
        traçable et sa fiabilité est suivie ; la déduplication évite les
        doublons inter-sources.
      </p>
      <ErrorNote error={error} />
      <div className="grid-2">
        <label className="field">
          <span>Nom de la source *</span>
          <input value={form.name} onChange={(e) => set("name", e.target.value)} required placeholder="Ex. Offres Emploi CM" />
        </label>
        <label className="field">
          <span>Type</span>
          <select value={form.kind} onChange={(e) => set("kind", e.target.value)}>
            <option value="rss">Flux RSS / Atom</option>
            <option value="json">API JSON</option>
          </select>
        </label>
      </div>
      <label className="field">
        <span>URL du flux / de l'API *</span>
        <input value={form.url} onChange={(e) => set("url", e.target.value)} required placeholder="https://…/feed.xml" />
      </label>
      <label className="field">
        <span>Secteur par défaut (si non détecté)</span>
        <input value={form.sector} onChange={(e) => set("sector", e.target.value)} placeholder="Ex. BTP / Construction" />
      </label>
      <div className="actions-row">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "…" : "Ajouter la source"}
        </button>
      </div>
    </form>
  );
}

function ImportUrlForm({ onDraft }) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setDraft(null);
    try {
      const res = await api("/admin/import-url", { method: "POST", body: { url } });
      setDraft(res);
      onDraft(res);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={submit}>
      <h2>Importer une offre depuis une URL (LinkedIn ou autre)</h2>
      <p className="small muted">
        Collez l'URL publique d'une offre : le système lit son balisage
        standard (JSON-LD) et propose un brouillon à vérifier avant
        publication. Mécanisme léger et autorisé : une page fournie par
        l'utilisateur, jamais de collecte de masse.
      </p>
      <ErrorNote error={error} />
      {draft && (
        <div className="alert alert-info">
          Brouillon extrait : {draft.title || "titre à préciser"} ·{" "}
          {draft.company || "entreprise à préciser"} ·{" "}
          {draft.location || "lieu à préciser"}. Vérifiez-le dans le
          formulaire « Nouvelle offre » ci-contre, puis publiez.
        </div>
      )}
      <label className="field">
        <span>URL de l'offre *</span>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
          placeholder="https://www.linkedin.com/jobs/view/…"
        />
      </label>
      <div className="actions-row">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Analyse…" : "Extraire l'offre"}
        </button>
      </div>
    </form>
  );
}

export default function AdminSources() {
  const [sources, setSources] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [running, setRunning] = useState(false);

  const reload = () => {
    api("/admin/sources").then(setSources).catch((e) => setError(e.detail));
  };

  useEffect(() => {
    reload();
  }, []);

  if (error && !sources) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!sources) {
    return <div className="page"><Loader /></div>;
  }

  async function run(sourceId) {
    setRunning(true);
    setNotice("");
    try {
      const res = await api(`/admin/sources/${sourceId}/run`, { method: "POST" });
      setNotice(
        `Résultat : ${res.imported} offre(s) importée(s), ${res.skipped} doublon(s) ignoré(s).`
      );
      reload();
    } catch (err) {
      setError(err.detail);
    } finally {
      setRunning(false);
    }
  }

  async function runAll() {
    setRunning(true);
    setNotice("Collecte en cours…");
    try {
      const results = await api("/admin/sources/run-all", { method: "POST" });
      const imported = results.reduce((a, r) => a + (r.imported || 0), 0);
      const errors = results.filter((r) => "error" in r).length;
      setNotice(`Collecte terminée : ${imported} offre(s) importée(s)${errors ? `, ${errors} source(s) en échec (détail dans la fiabilité)` : ""}.`);
      reload();
    } catch (err) {
      setError(err.detail);
    } finally {
      setRunning(false);
    }
  }

  async function remove(source) {
    if (!window.confirm(`Supprimer la source « ${source.name} » ?`)) return;
    try {
      await api(`/admin/sources/${source.id}`, { method: "DELETE" });
      reload();
    } catch (err) {
      setError(err.detail);
    }
  }

  return (
    <div className="page">
      <h1>Sources & collecte</h1>
      <p className="page-lead">
        Architecture multi-source à connecteurs interchangeables : collecte,
        normalisation, déduplication et scoring de fiabilité (§50-51).
      </p>
      {notice && <div className="alert alert-success">{notice}</div>}
      <ErrorNote error={error} />

      <ImportUrlForm onDraft={() => {}} />
      <AddSourceForm onSaved={reload} />

      <div className="actions-row">
        <button className="btn btn-primary" onClick={runAll} disabled={running || sources.length === 0}>
          {running ? "Collecte en cours…" : "Lancer la collecte de toutes les sources actives"}
        </button>
      </div>

      {sources.length === 0 && (
        <Empty title="Aucune source configurée">
          <p>Ajoutez un flux RSS ou une API JSON pour automatiser la collecte.</p>
        </Empty>
      )}

      {sources.map((s) => (
        <div className="app-row" key={s.id}>
          <div className="app-head">
            <div>
              <strong>{s.name}</strong>
              <p className="job-meta" style={{ margin: "0.15rem 0" }}>
                {s.kind === "rss" ? "Flux RSS" : "API JSON"} · {s.sector || "tous secteurs"}
              </p>
              <p className="small muted" style={{ margin: 0, wordBreak: "break-all" }}>
                {s.url}
              </p>
            </div>
            <div className="actions-row" style={{ marginTop: 0 }}>
              <span className={`badge ${s.enabled ? "badge-strong" : "badge-none"}`}>
                {s.enabled ? "Active" : "Désactivée"}
              </span>
              <button className="btn btn-outline btn-small" onClick={() => run(s.id)} disabled={running}>
                Collecter
              </button>
              <button className="btn btn-ghost btn-small" onClick={() => remove(s)}>
                Supprimer
              </button>
            </div>
          </div>
          <p className="small muted" style={{ marginTop: "0.4rem" }}>
            Fiabilité : {s.reliability} · {s.offers_imported} offre(s) importée(s) ·{" "}
            {s.offers_skipped} doublon(s) ·{" "}
            {s.last_run_at ? `dernière exécution : ${fmtDateTime(s.last_run_at)}` : "jamais exécutée"}
            {s.last_status ? ` · ${s.last_status}` : ""}
          </p>
        </div>
      ))}
    </div>
  );
}
