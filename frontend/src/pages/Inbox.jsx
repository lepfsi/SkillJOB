import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { relTime, fmtDateTime } from "../lib.js";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";

// Inbox (§28) : événements importants groupés par jour.
const KIND_LABELS = {
  new_job: "Nouvelle offre",
  strong_match: "Correspondance forte",
  trend: "Marché",
  learning: "Formation",
  application: "Candidature",
};

export default function Inbox() {
  const [events, setEvents] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/inbox").then(setEvents).catch((e) => setError(e.detail));
  }, []);

  if (error) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!events) {
    return <div className="page"><Loader /></div>;
  }
  if (events.length === 0) {
    return (
      <div className="page">
        <h1>Inbox</h1>
        <Empty title="Aucun événement pour le moment">
          <p>
            Dès qu'une offre correspondant à votre profil apparaîtra, vous la
            retrouverez ici. Complétez votre profil pour recevoir des
            recommandations pertinentes.
          </p>
          <Link className="btn btn-outline" to="/opportunites">Parcourir les opportunités</Link>
        </Empty>
      </div>
    );
  }

  const groups = [];
  let current = null;
  for (const ev of events) {
    const label = relTime(ev.at);
    if (!current || current.label !== label) {
      current = { label, items: [] };
      groups.push(current);
    }
    current.items.push(ev);
  }

  return (
    <div className="page page-narrow">
      <h1>Inbox</h1>
      {groups.map((g) => (
        <section className="section" key={g.label}>
          <div className="section-head">
            <h2>{g.label}</h2>
          </div>
          {g.items.map((ev) => (
            <div key={ev.id} className="app-row">
              <div className="app-head">
                <div>
                  <span className="small muted">{fmtDateTime(ev.at)} · {KIND_LABELS[ev.kind] || ev.kind}</span>
                  <p>{ev.message}</p>
                </div>
                {ev.job_id && (
                  <Link className="btn btn-outline btn-small" to={`/opportunites/${ev.job_id}`}>
                    Voir l'offre
                  </Link>
                )}
              </div>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
