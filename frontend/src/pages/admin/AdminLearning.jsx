import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";

// Catalogue des formations (§19) : le référentiel JSON alimente les
// entrées « referentiel » ; la console ajoute les siennes (« admin »),
// jamais écrasées par la synchronisation du démarrage.

const TYPE_LABELS = {
  course: "Cours",
  certification: "Certification",
  project: "Projet",
  free: "Ressource libre",
};

const EMPTY_FORM = {
  skill: "",
  title: "",
  provider: "",
  type: "course",
  url: "",
  hidden: false,
};

export default function AdminLearning() {
  const [rows, setRows] = useState(null);
  const [form, setForm] = useState(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = () => {
    api("/admin/learning").then(setRows).catch((e) => setError(e.detail));
  };

  useEffect(() => {
    reload();
  }, []);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (form.id) {
        const updated = await api(`/admin/learning/${form.id}`, {
          method: "PUT",
          body: {
            skill: form.skill,
            title: form.title,
            provider: form.provider,
            type: form.type,
            url: form.url,
            hidden: Boolean(form.hidden),
          },
        });
        setNotice(
          updated.source === "admin"
            ? `Formation « ${updated.title} » mise à jour (version console).`
            : `Formation « ${updated.title} » mise à jour.`
        );
      } else {
        const created = await api("/admin/learning", { method: "POST", body: form });
        setNotice(`Formation « ${created.title} » ajoutée au catalogue.`);
      }
      setForm(null);
      reload();
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function remove(row) {
    const isReferentiel = row.source !== "admin";
    const question = isReferentiel
      ? `Retirer « ${row.title} » (${row.skill}) du catalogue ?`
      : `Supprimer « ${row.title} » (${row.skill}) du catalogue ?`;
    if (!window.confirm(question)) {
      return;
    }
    try {
      const result = await api(`/admin/learning/${row.id}`, { method: "DELETE" });
      setNotice(
        result.hidden
          ? `Formation « ${row.title} » retirée du catalogue (rétablissable).`
          : `Formation « ${row.title} » supprimée.`
      );
      setError("");
      reload();
    } catch (err) {
      setError(err.detail);
    }
  }

  async function restore(row) {
    try {
      await api(`/admin/learning/${row.id}/restore`, { method: "POST" });
      setNotice(`Formation « ${row.title} » rétablie dans le catalogue.`);
      setError("");
      reload();
    } catch (err) {
      setError(err.detail);
    }
  }

  if (!rows) {
    return <div className="page"><Loader /></div>;
  }

  const needle = query.trim().toLowerCase();
  const visible = rows.filter((r) => (
    !needle
    || [r.skill, r.title, r.provider].filter(Boolean).join(" ").toLowerCase().includes(needle)
  ));
  const adminCount = rows.filter((r) => r.source === "admin").length;
  const hiddenCount = rows.filter((r) => r.hidden).length;

  return (
    <div className="page">
      <h1>Formations</h1>
      <p className="page-lead">
        Catalogue proposé aux candidats : {rows.length} formation(s), dont
        {" "}{adminCount} ajoutée(s) depuis cette console
        {hiddenCount > 0 ? ` et ${hiddenCount} masquée(s)` : ""}.
        {" "}Une ligne du référentiel modifiée ici devient une version console.
      </p>

      {notice && <div className="alert alert-success">{notice}</div>}
      <ErrorNote error={error} />

      <div className="actions-row">
        <button
          className="btn btn-primary"
          onClick={() => { setForm({ ...EMPTY_FORM }); setError(""); }}
        >
          Ajouter une formation
        </button>
      </div>

      {form && (
        <form className="panel" onSubmit={save}>
          <h2>{form.id ? "Modifier la formation" : "Nouvelle formation"}</h2>
          <p className="small muted">
            La compétence cible la clé du plan d'apprentissage des candidats.
            Le lien peut être la formation exacte, un catalogue ou une
            recherche : sa nature est indiquée honnêtement au candidat.
          </p>
          <div className="grid-2">
            <label className="field">
              <span>Compétence ciblée *</span>
              <input
                value={form.skill}
                onChange={(e) => set("skill", e.target.value)}
                placeholder="Ex. Excel avancé"
                required
              />
            </label>
            <label className="field">
              <span>Type *</span>
              <select value={form.type} onChange={(e) => set("type", e.target.value)}>
                <option value="course">Cours</option>
                <option value="certification">Certification</option>
                <option value="project">Projet guidé</option>
                <option value="free">Ressource libre</option>
              </select>
            </label>
            <label className="field">
              <span>Intitulé *</span>
              <input
                value={form.title}
                onChange={(e) => set("title", e.target.value)}
                placeholder="Ex. Analyse de données avec Excel"
                required
              />
            </label>
            <label className="field">
              <span>Fournisseur</span>
              <input
                value={form.provider}
                onChange={(e) => set("provider", e.target.value)}
                placeholder="Ex. Coursera, OpenClassrooms, université de Douala"
              />
            </label>
          </div>
          <label className="field">
            <span>Lien (URL)</span>
            <input
              value={form.url}
              onChange={(e) => set("url", e.target.value)}
              placeholder="https://…"
            />
          </label>
          <div className="actions-row">
            <button className="btn btn-primary" disabled={busy}>
              {busy ? "Enregistrement…" : form.id ? "Mettre à jour" : "Ajouter au catalogue"}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setForm(null)}>
              Annuler
            </button>
          </div>
        </form>
      )}

      <div className="filters">
        <label className="field">
          <span>Rechercher</span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Compétence, intitulé, fournisseur…"
          />
        </label>
      </div>

      {visible.length === 0 ? (
        <Empty title="Aucune formation">
          <p>Ajustez la recherche ou ajoutez une première formation.</p>
        </Empty>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Compétence</th>
              <th>Intitulé</th>
              <th>Type</th>
              <th>Fournisseur</th>
              <th>Lien</th>
              <th>Origine</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => (
              <tr key={r.id}>
                <td><strong>{r.skill}</strong></td>
                <td>{r.title}</td>
                <td>{TYPE_LABELS[r.type] || r.type}</td>
                <td>{r.provider || <span className="muted small">Non renseigné</span>}</td>
                <td>
                  {r.url ? (
                    <a href={r.url} target="_blank" rel="noreferrer" className="link-more">
                      Ouvrir le lien
                    </a>
                  ) : (
                    <span className="muted small">Sans lien</span>
                  )}
                </td>
                <td>
                  {r.source === "admin"
                    ? <span className="badge badge-strong">Console</span>
                    : <span className="badge badge-none">Référentiel</span>}
                  {r.hidden && (
                    <span className="badge badge-weak" style={{ marginLeft: "0.3rem" }}>
                      Masquée
                    </span>
                  )}
                </td>
                <td>
                  <div className="admin-apply-links">
                    <button
                      type="button"
                      className="btn btn-outline btn-small"
                      onClick={() => {
                        setForm({ ...r });
                        setError("");
                        window.scrollTo({ top: 0, behavior: "smooth" });
                      }}
                    >
                      Modifier
                    </button>
                    {r.hidden ? (
                      <button
                        type="button"
                        className="btn btn-small"
                        onClick={() => restore(r)}
                      >
                        Rétablir
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-remove btn-small"
                        onClick={() => remove(r)}
                      >
                        {r.source === "admin" ? "Supprimer" : "Retirer"}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
