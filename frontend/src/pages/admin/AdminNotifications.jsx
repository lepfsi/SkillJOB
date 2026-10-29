import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client.js";
import { fmtDateTime } from "../../lib.js";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";

// Boîte de réception des notifications administratives (§21).
// L'admin filtre par catégorie, état de lecture et résultat d'envoi, puis
// marque comme lu, archive ou supprime une notification. Chaque ligne renvoie
// vers l'action métier concernée via href.
const STATUS_FILTERS = [
  ["all", "Toutes"],
  ["unread", "Non lues"],
  ["read", "Lues"],
  ["archived", "Archivées"],
];
const DELIVERY_FILTERS = [
  ["all", "Tous envois"],
  ["sent", "Envoyés"],
  ["partial", "Partiels"],
  ["failed", "Échecs"],
  ["recorded", "Consignés uniquement"],
];
const STATUS_TONE = { sent: "ok", partial: "wait", failed: "ko", recorded: "muted" };

export default function AdminNotifications() {
  const navigate = useNavigate();
  const [page, setPage] = useState(null);
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState("all");
  const [delivery, setDelivery] = useState("all");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [limit, setLimit] = useState(30);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState("");

  const params = () => {
    const p = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (category !== "all") p.set("category", category);
    if (status !== "all") p.set("status", status);
    if (delivery !== "all") p.set("delivery", delivery);
    if (since) p.set("since", since);
    if (until) p.set("until", until);
    return p.toString();
  };

  function load() {
    setBusy(true);
    setError("");
    api(`/admin/notifications?${params()}`)
      .then((data) => {
        setPage(data);
      })
      .catch((err) => setError(err.detail || "Chargement impossible"))
      .finally(() => setBusy(false));
  }

  useEffect(() => {
    load();
  }, [category, status, delivery, since, until, limit, offset]);

  function categoryLabel(key) {
    const found = (page?.categories || []).find((c) => c.key === key);
    return found ? found.label : key;
  }

  async function toggleRead(row) {
    setError("");
    try {
      await api(`/admin/notifications/${row.id}/mark-read`, { method: "POST" });
      setFlash(row.is_unread ? "Marquée comme lue." : "Marquée comme non lue.");
      await load();
    } catch (err) {
      setError(err.detail || "Marquage impossible");
    }
  }

  async function toggleArchive(row) {
    setError("");
    try {
      await api(`/admin/notifications/${row.id}/mark-deleted`, { method: "PUT" });
      setFlash("Archivée.");
      await load();
    } catch (err) {
      setError(err.detail || "Archivage impossible");
    }
  }

  async function removeNotification(row) {
    if (!window.confirm("Supprimer cette notification du journal ?")) return;
    setError("");
    try {
      await api(`/admin/notifications/${row.id}`, { method: "DELETE" });
      setFlash("Supprimée.");
      await load();
      if (page?.items.length === 0 && offset > 0) setOffset(Math.max(0, offset - limit));
    } catch (err) {
      setError(err.detail || "Suppression impossible");
    }
  }

  function goPage(delta) {
    setOffset(Math.max(0, offset + delta * limit));
  }

  if (error && !page) return <div className="page"><ErrorNote error={error} /></div>;
  if (!page) return <div className="page"><Loader /></div>;
  return (
    <div className="page">
      <h1>Notifications administratives</h1>
      <p className="page-lead">
        Boîte de réception centralisée : demandes de vérification, recours, signalements,
        échecs de collecte et alertes critiques. Conserver {page.retention_days ?? 90} jours.
      </p>

      <div className="stats-strip">
        <div className="stat-tile"><span>Total</span><strong>{page.total}</strong></div>
        <div className="stat-tile"><span>Non lues</span><strong>{page.unread}</strong></div>
        {Object.entries(page.per_category || {}).map(([key, counts]) => (
          <div key={key} className="stat-tile">
            <span>{categoryLabel(key)}</span><strong>{counts.total}</strong>
          </div>
        ))}
      </div>

      {flash && <div className="alert alert-success">{flash}</div>}
      <ErrorNote error={error} />

      <div className="filters-row">
        <div className="filter-group">
          <label>Catégorie</label>
          <select value={category} onChange={(e) => { setError(""); setCategory(e.target.value); setOffset(0); }}>
            <option value="all">Toutes les catégories</option>
            {(page.categories || []).map((c) => (
              <option key={c.key} value={c.key}>{c.label}</option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label>État</label>
          <select value={status} onChange={(e) => { setError(""); setStatus(e.target.value); setOffset(0); }}>
            {STATUS_FILTERS.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label>Envoi</label>
          <select value={delivery} onChange={(e) => { setError(""); setDelivery(e.target.value); setOffset(0); }}>
            {DELIVERY_FILTERS.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label>Depuis</label>
          <input type="date" value={since} onChange={(e) => { setError(""); setSince(e.target.value); setOffset(0); }} />
        </div>
        <div className="filter-group">
          <label>Jusqu'au</label>
          <input type="date" value={until} onChange={(e) => { setError(""); setUntil(e.target.value); setOffset(0); }} />
        </div>
      </div>
      {page.items.length === 0 ? (
        <Empty title="Aucune notification">
          <p>Aucune alerte administrative ne correspond aux filtres sélectionnés.</p>
        </Empty>
      ) : (
        <div className="table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Objet</th>
                <th>Catégorie</th>
                <th>État</th>
                <th>Envoi</th>
                <th>Destinataires</th>
                <th>Créée le</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {page.items.map((row) => (
                <tr key={row.id}>
                  <td>
                    <Link to={row.href || "/admin/equipe-alertes"} title={row.subject}>
                      {row.subject}
                    </Link>
                    {row.body && <p className="small muted">{row.body}</p>}
                  </td>
                  <td>{categoryLabel(row.category)}</td>
                  <td>
                    <span className={`badge ${row.is_unread ? "badge-unread" : "badge-read"}`}>
                      {row.is_unread ? "Non lue" : "Lue"}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${STATUS_TONE[row.status] || "muted"}`}>
                      {row.status === "sent" ? "Envoyé" : row.status === "partial" ? "Partiel" : row.status === "failed" ? "Échec" : "Consigné"}
                    </span>
                    <span className="small muted"> ({row.sent_count} ok{row.failed_count ? ` · ${row.failed_count} échec(s)` : ""})</span>
                  </td>
                  <td>{(row.recipients || []).join(", ") || "—"}</td>
                  <td>{row.created_at ? fmtDateTime(row.created_at) : "—"}</td>
                  <td>
                    {!row.is_unread && (
                      <button type="button" className="btn btn-small btn-outline" onClick={() => toggleRead(row)} disabled={busy}>
                        Marquer non lue
                      </button>
                    )}
                    {row.is_unread && (
                      <button type="button" className="btn btn-small" onClick={() => toggleRead(row)} disabled={busy}>
                        Marquer lue
                      </button>
                    )}
                    {!row.archived_at && (
                      <button type="button" className="btn btn-small btn-outline" style={{ marginLeft: 6 }} onClick={() => toggleArchive(row)} disabled={busy || row.archived_at}>
                        Archiver
                      </button>
                    )}
                    <button type="button" className="btn btn-small btn-remove" style={{ marginLeft: 6 }} onClick={() => removeNotification(row)} disabled={busy}>
                      Supprimer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="pagination">
        <button type="button" className="btn btn-small btn-outline" disabled={offset === 0 || busy} onClick={() => goPage(-1)}>
          Précédente
        </button>
        <span className="small muted"> {offset + 1} – {Math.min(offset + page.items.length, page.total)} / {page.total} </span>
        <button type="button" className="btn btn-small btn-outline" disabled={page.items.length < limit || busy} onClick={() => goPage(1)}>
          Suivante
        </button>
      </div>
    </div>
  );
}