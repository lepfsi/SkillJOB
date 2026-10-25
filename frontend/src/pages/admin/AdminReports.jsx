import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import { fmtDate } from "../../lib.js";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";

// Traitement des signalements d'offres. Un signalement garde son auteur,
// son motif et la note de décision : rien n'est supprimé.

const REASON_LABELS = {
  arnaque: "Offre frauduleuse ou demande d'argent",
  contenu_trompeur: "Contenu trompeur ou incohérent",
  offre_expiree: "Offre expirée ou déjà pourvue",
  discrimination: "Discrimination ou propos inapproprié",
  doublon: "Doublon d'une autre offre",
  autre: "Autre problème",
};

const STATUS_LABELS = {
  nouveau: "Nouveau",
  en_cours: "En cours",
  traite: "Traité",
  rejete: "Rejeté",
};

function ReportCard({ report, onSaved }) {
  const [status, setStatus] = useState(report.status);
  const [note, setNote] = useState(report.admin_note || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");

  async function save() {
    setBusy(true);
    setError("");
    setFlash("");
    try {
      const updated = await api(`/admin/reports/${report.id}`, {
        method: "PUT",
        body: { status, admin_note: note },
      });
      setFlash("Signalement mis à jour.");
      onSaved(updated);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="panel report-card">
      <div className="report-card-head">
        <div>
          <span className={`report-status report-status-${report.status}`}>
            {STATUS_LABELS[report.status] || report.status}
          </span>
          <h2>{REASON_LABELS[report.reason] || report.reason}</h2>
          <p className="muted small">
            {report.user_name || "Candidat"} · {report.user_email} ·{" "}
            {fmtDate(report.created_at)}
          </p>
        </div>
        <Link
          className="btn btn-outline btn-small"
          to={`/opportunites/${report.job_id}`}
          target="_blank"
          rel="noreferrer"
        >
          Voir l'offre
        </Link>
      </div>

      <div className="report-job">
        <strong>{report.job_title || `Offre ${report.job_id}`}</strong>
        {report.company && <span className="muted"> · {report.company}</span>}
      </div>
      {report.details && <p className="report-details">{report.details}</p>}

      <div className="report-treatment">
        <label className="field">
          <span>Statut du traitement</span>
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Note interne / réponse au candidat</span>
          <textarea
            rows="2"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Décision, vérification effectuée, suite donnée."
          />
        </label>
        <button className="btn btn-primary btn-small" onClick={save} disabled={busy}>
          {busy ? "Enregistrement…" : "Enregistrer le traitement"}
        </button>
      </div>
      <ErrorNote error={error} />
      {flash && <div className="alert alert-success small">{flash}</div>}
    </article>
  );
}

export default function AdminReports() {
  const [reports, setReports] = useState(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [stats, setStats] = useState(null);

  useEffect(() => {
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    api(`/admin/reports${query}`)
      .then((rows) => setReports(rows || []))
      .catch((err) => setError(err.detail));
  }, [status]);

  useEffect(() => {
    api("/admin/stats").then(setStats).catch(() => setStats(null));
  }, []);

  function updateReport(updated) {
    setReports((rows) => (rows || []).map((row) => (
      row.id === updated.id ? updated : row
    )));
  }

  if (error && !reports) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!reports) {
    return <div className="page"><Loader /></div>;
  }

  return (
    <div className="page">
      <h1>Signalements d'offres</h1>
      <p className="page-lead">
        Vérifiez chaque signalement, consultez l'offre concernée puis
        enregistrez une décision. Le candidat retrouve le statut et votre note
        sur la fiche de l'offre.
      </p>

      {stats && (
        <div className="stats-strip report-stats">
          <div className="stat-tile">
            <span>Signalements à traiter</span>
            <strong>{stats.open_reports ?? 0}</strong>
          </div>
        </div>
      )}

      <div className="segmented-row" role="tablist" aria-label="Filtrer les signalements">
        {[
          ["", "Tous"],
          ["nouveau", "Nouveaux"],
          ["en_cours", "En cours"],
          ["traite", "Traités"],
          ["rejete", "Rejetés"],
        ].map(([value, label]) => (
          <button
            key={value || "all"}
            type="button"
            className={`btn btn-small ${status === value ? "btn-primary" : "btn-outline"}`}
            onClick={() => {
              setError("");
              setStatus(value);
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <ErrorNote error={error} />
      {reports.length === 0 ? (
        <Empty title="Aucun signalement">
          <p>Les signalements envoyés par les candidats apparaîtront ici.</p>
        </Empty>
      ) : (
        <div className="report-list">
          {reports.map((report) => (
            <ReportCard key={report.id} report={report} onSaved={updateReport} />
          ))}
        </div>
      )}
    </div>
  );
}
