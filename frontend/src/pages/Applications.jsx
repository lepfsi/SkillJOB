import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import {
  STATUS_ORDER,
  STATUS_LABELS,
  fmtDateTime,
  fmtDate,
} from "../lib.js";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";

// Page Applications (§36) : mini-ATS personnel. Chaque candidature
// affiche son pipeline (identifiée → … → acceptée), ses documents liés
// et son historique daté.

function Pipeline({ current }) {
  const currentIdx = STATUS_ORDER.indexOf(current);
  return (
    <div className="pipeline">
      {STATUS_ORDER.map((s, i) => (
        <span key={s} style={{ display: "flex", alignItems: "center", flex: "0 0 auto" }}>
          <span
            className={`pipeline-step ${
              i < currentIdx ? "done" : i === currentIdx ? "current" : ""
            }`}
          >
            <span className="pipeline-dot" />
            {STATUS_LABELS[s]}
          </span>
          {i < STATUS_ORDER.length - 1 && <span className="pipeline-link" />}
        </span>
      ))}
    </div>
  );
}

export default function Applications() {
  const [apps, setApps] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/applications").then(setApps).catch((e) => setError(e.detail));
  }, []);

  async function changeStatus(appId, status) {
    try {
      const updated = await api(`/applications/${appId}`, {
        method: "PATCH",
        body: { status },
      });
      setApps((list) => list.map((a) => (a.id === appId ? updated : a)));
    } catch (err) {
      setError(err.detail);
    }
  }

  if (error && !apps) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!apps) {
    return <div className="page"><Loader /></div>;
  }

  const active = apps.filter((a) => !["acceptee", "refusee"].includes(a.status));
  const closed = apps.filter((a) => ["acceptee", "refusee"].includes(a.status));

  const renderApp = (app) => {
    const currentIdx = STATUS_ORDER.indexOf(app.status);
    const nextStatus = STATUS_ORDER[currentIdx + 1];
    return (
      <div className="app-row" key={app.id}>
        <div className="app-head">
          <div>
            <strong>{app.job.title}</strong>
            <p className="job-meta" style={{ margin: "0.15rem 0" }}>
              {app.job.company} · {app.job.location} · {app.job.contract_type}
            </p>
            <p className="small muted" style={{ margin: 0 }}>
              Offre publiée le {fmtDate(app.job.published_at)}
            </p>
          </div>
          <div className="actions-row" style={{ marginTop: 0 }}>
            {nextStatus && (
              <button
                className="btn btn-primary btn-small"
                onClick={() => changeStatus(app.id, nextStatus)}
              >
                Passer à « {STATUS_LABELS[nextStatus]} »
              </button>
            )}
            <select
              value={app.status}
              onChange={(e) => changeStatus(app.id, e.target.value)}
              style={{ width: "auto" }}
            >
              {STATUS_ORDER.map((s) => (
                <option key={s} value={s}>{STATUS_LABELS[s]}</option>
              ))}
            </select>
            <Link className="btn btn-ghost btn-small" to={`/opportunites/${app.job_id}`}>
              Voir l'offre
            </Link>
          </div>
        </div>

        <Pipeline current={app.status} />

        {app.documents.length > 0 && (
          <div className="chip-row" style={{ marginTop: "0.5rem" }}>
            {app.documents.map((d) => (
              <Link key={d.id} className="chip" to={`/documents?open=${d.id}`}>
                {d.kind === "cv" ? "CV ciblé" : "Lettre"} : {d.title.split(" · ").slice(1).join(" · ")}
              </Link>
            ))}
          </div>
        )}

        {app.timeline.length > 0 && (
          <ul className="timeline">
            {[...app.timeline].reverse().map((ev, i) => (
              <li key={i}>{fmtDateTime(ev.at)} · {ev.event}</li>
            ))}
          </ul>
        )}
      </div>
    );
  };

  return (
    <div className="page">
      <h1>Candidatures</h1>
      <p className="page-lead">
        Suivez l'avancement de vos candidatures et marquez chaque étape
        franchie : l'historique reste daté et vérifiable.
      </p>
      <ErrorNote error={error} />

      {apps.length === 0 && (
        <Empty title="Aucune candidature suivie">
          <p>
            Repérez une offre intéressante puis cliquez sur « Suivre ma
            candidature » pour l'ajouter à votre pipeline.
          </p>
          <Link className="btn btn-outline" to="/opportunites">Parcourir les opportunités</Link>
        </Empty>
      )}

      {active.length > 0 && (
        <section className="section">
          <div className="section-head">
            <h2>En cours ({active.length})</h2>
          </div>
          {active.map(renderApp)}
        </section>
      )}

      {closed.length > 0 && (
        <section className="section">
          <div className="section-head">
            <h2>Clôturées ({closed.length})</h2>
          </div>
          {closed.map(renderApp)}
        </section>
      )}
    </div>
  );
}
