import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { RESOURCE_TYPE_LABELS } from "../lib.js";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";

// Page Learning (§34) : catalogue personnalisé + progression VÉRIFIABLE.
// Chaque compétence affiche ses preuves (expériences, projets,
// certifications) et la prochaine étape concrète pour la consolider.

const EVIDENCE_KIND_LABELS = {
  experience: "Expérience",
  project: "Projet",
  certification: "Certification",
  education: "Formation",
};

function LearningCard({ item }) {
  return (
    <div className="panel-light">
      <h3>{item.skill}</h3>
      <p className="small muted">{item.reason}</p>
      {item.resources.length > 0 ? (
        <ul className="explain-list">
          {item.resources.map((r) => (
            <li key={r.title}>
              {r.url ? (
                <a href={r.url} target="_blank" rel="noreferrer">{r.title}</a>
              ) : (
                r.title
              )}
              {" "}
              <span className="small muted">
                · {r.provider} · {RESOURCE_TYPE_LABELS[r.type] || r.type}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="small muted">Aucune ressource référencée pour cette compétence.</p>
      )}
    </div>
  );
}

function ProgressCard({ p }) {
  return (
    <div className="progress-card">
      <div className="progress-card-head">
        <h3>{p.skill}</h3>
        <span className={`badge ${p.status === "verifiee" ? "badge-strong" : p.status === "en_progression" ? "badge-medium" : "badge-none"}`}>
          {p.status_label}
        </span>
      </div>
      <p className="progress-demand">
        Niveau {p.level} · demandée par {p.demand} offre(s) active(s)
      </p>
      {p.evidences.length > 0 ? (
        <div>
          {p.evidences.map((e, i) => (
            <span key={i} className="evidence-chip">
              {EVIDENCE_KIND_LABELS[e.kind] || e.kind} : {e.label}
            </span>
          ))}
        </div>
      ) : (
        <p className="evidence-empty">Aucune preuve rattachée pour l'instant.</p>
      )}
      <p className="next-step">{p.next_step}</p>
    </div>
  );
}

export default function Learning() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/learning").then(setData).catch((e) => setError(e.detail));
  }, []);

  if (error && !data) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!data) {
    return <div className="page"><Loader /></div>;
  }

  const empty = data.learn_now.length === 0 && data.learn_next.length === 0
    && !(data.improve || []).length;
  const verified = data.progress.filter((p) => p.status === "verifiee").length;

  return (
    <div className="page">
      <h1>Learning</h1>
      <p className="page-lead">
        Recommandations adaptées à VOTRE trajectoire : les compétences
        manquantes de vos métiers recommandés, le perfectionnement de votre
        domaine de force, puis les autres écarts face au marché.
        Sources reconnues : OpenClassrooms, Coursera, edX, freeCodeCamp,
        Microsoft Learn, Google, Cisco, AWS, HubSpot.
      </p>
      <ErrorNote error={error} />

      {empty && (
        <Empty title="Aucun écart de compétences détecté">
          <p>
            Votre profil couvre les compétences principales des offres
            actuelles, ou votre profil n'est pas encore construit.
          </p>
          <Link className="btn btn-outline" to="/profil">Vérifier mon profil</Link>
        </Empty>
      )}

      {data.learn_now.length > 0 && (
        <section className="section">
          <div className="section-head">
            <h2>À apprendre maintenant</h2>
          </div>
          {data.learn_now.map((item) => <LearningCard key={item.skill} item={item} />)}
        </section>
      )}

      {data.improve && data.improve.length > 0 && (
        <section className="section">
          <div className="section-head">
            <h2>Perfectionner mon domaine</h2>
            <span className="small muted">vos acquis, consolidés par des preuves reconnues</span>
          </div>
          {data.improve.map((item) => <LearningCard key={item.skill} item={item} />)}
        </section>
      )}

      {data.learn_next.length > 0 && (
        <section className="section">
          <div className="section-head">
            <h2>À apprendre ensuite</h2>
          </div>
          {data.learn_next.map((item) => <LearningCard key={item.skill} item={item} />)}
        </section>
      )}

      {data.progress.length > 0 && (
        <section className="section">
          <div className="section-head">
            <h2>Progression vérifiable</h2>
            <span className="small muted">
              {verified} compétence(s) appuyée(s) par des preuves sur {data.progress.length}
            </span>
          </div>
          <p className="small muted">
            Une compétence avec des preuves issues de votre profil pèse plus
            dans le matching : rattachez des expériences, projets ou
            certifications à vos compétences depuis la page{" "}
            <Link to="/profil">Profil</Link>.
          </p>
          <div className="progress-grid">
            {data.progress.map((p) => <ProgressCard key={p.skill} p={p} />)}
          </div>
        </section>
      )}
    </div>
  );
}
