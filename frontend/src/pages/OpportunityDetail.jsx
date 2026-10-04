import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client.js";
import MatchBadge from "../components/MatchBadge.jsx";
import ScoreBar from "../components/ScoreBar.jsx";
import SkillTag from "../components/SkillTag.jsx";
import { fmtDate } from "../lib.js";
import { Loader, ErrorNote } from "../components/ui.jsx";

// Page Opportunity Detail (§30) : description, compétences requises,
// match explicable (✓ couverte / △ partielle / ○ manquante), actions.
export default function OpportunityDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null); // { job, match }
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const [prep, setPrep] = useState(null);
  const [templates, setTemplates] = useState(undefined); // undefined = fermé, null = chargement

  useEffect(() => {
    api(`/jobs/${id}`)
      .then(setData)
      .catch((e) => setError(e.detail));
  }, [id]);

  async function doAction(kind) {
    setActionError("");
    setBusyAction(kind);
    try {
      if (kind === "cv") {
        setTemplates(null);
        const list = await api("/cv-templates");
        setTemplates(list);
      } else if (kind === "letter") {
        const doc = await api(`/jobs/${id}/cover-letter`, { method: "POST" });
        navigate(`/documents?open=${doc.id}`);
      } else if (kind === "prep") {
        setPrep(await api(`/jobs/${id}/interview-prep`, { method: "POST" }));
      } else if (kind === "apply") {
        await api("/applications", { method: "POST", body: { job_id: Number(id) } });
        navigate("/candidatures");
      }
    } catch (err) {
      setActionError(err.detail);
    } finally {
      setBusyAction("");
    }
  }

  async function generateCv(templateId) {
    setBusyAction("cv");
    setActionError("");
    try {
      const doc = await api(`/jobs/${id}/cv`, {
        method: "POST",
        body: { template: templateId },
      });
      navigate(`/documents?open=${doc.id}`);
    } catch (err) {
      setActionError(err.detail);
      setBusyAction("");
    }
  }

  if (error) {
    return (
      <div className="page">
        <ErrorNote error={error} />
        <Link to="/opportunites" className="btn btn-ghost">← Retour aux opportunités</Link>
      </div>
    );
  }
  if (!data) {
    return <div className="page"><Loader /></div>;
  }

  const { job, match } = data;

  return (
    <div className="page">
      <Link to="/opportunites" className="small">← Retour aux opportunités</Link>

      <div className="job-head" style={{ marginTop: "0.6rem" }}>
        <div>
          <h1>{job.title}</h1>
          <p className="muted" style={{ margin: 0 }}>
            {job.company} · {job.location} · {job.contract_type}
            {job.salary ? ` · ${job.salary}` : ""}
          </p>
          <p className="job-source">
            Publiée le {fmtDate(job.published_at)} · Source :{" "}
            <a href={job.source.url} target="_blank" rel="noreferrer">
              {job.source.name}
            </a>
          </p>
        </div>
        {match && <MatchBadge score={match.score} />}
      </div>

      <section className="section">
        <h2>Description</h2>
        {(job.description || "").split("\n").filter(Boolean).map((p, i) => (
          <p key={i}>{p}</p>
        ))}
        {job.requirements && (
          <>
            <h3>Profil recherché</h3>
            {job.requirements.split("\n").filter(Boolean).map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </>
        )}
        <h3>Compétences requises</h3>
        <div className="chip-row">
          {(job.required_skills || []).map((rs) => (
            <SkillTag key={rs.name} name={rs.name} state="neutral" importance={rs.importance} />
          ))}
        </div>
      </section>

      {match ? (
        <section className="match-block">
          <h2>Match avec mon profil</h2>

          <ScoreBar
            score={match.score}
            covered={match.covered.length}
            partial={match.partial.length}
            missing={match.missing.length}
          />

          {match.covered.length > 0 && (
            <div className="chip-row">
              {match.covered.map((s) => <SkillTag key={s} name={s} state="covered" />)}
            </div>
          )}
          {match.partial.length > 0 && (
            <div className="chip-row">
              {match.partial.map((s) => <SkillTag key={s} name={s} state="partial" />)}
            </div>
          )}
          {match.missing.length > 0 && (
            <div className="chip-row">
              {match.missing.map((s) => <SkillTag key={s} name={s} state="missing" />)}
            </div>
          )}

          {match.strengths.length > 0 && (
            <>
              <h3>Points forts</h3>
              <ul className="explain-list">
                {match.strengths.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </>
          )}

          <h3>Pourquoi cette offre ?</h3>
          <p>{match.explanation}</p>

          {match.recommended_actions.length > 0 && (
            <>
              <h3>Ce que je dois améliorer</h3>
              <ul className="explain-list">
                {match.recommended_actions.map((a, i) => <li key={i}>{a}</li>)}
              </ul>
            </>
          )}

          {match.missing.length > 0 && (
            <div className="alert alert-info" style={{ marginTop: "0.6rem" }}>
              Il vous manque {match.missing.length} compétence(s) pour cette
              offre ({match.missing.slice(0, 3).join(", ")}
              {match.missing.length > 3 ? "…" : ""}).
              {" "}
              <Link className="btn btn-accent btn-small" to="/learning" style={{ marginLeft: "0.5rem" }}>
                Améliorer mes compétences
              </Link>
            </div>
          )}
        </section>
      ) : (
        <div className="alert alert-info">
          Complétez votre profil pour obtenir une analyse de correspondance
          détaillée. <Link to="/onboarding">Construire mon profil →</Link>
        </div>
      )}

      <ErrorNote error={actionError} />
      {actionError && actionError.includes("Profil requis") && (
        <Link to="/onboarding" className="btn btn-primary">Construire mon profil</Link>
      )}

      <div className="actions-row">
        <button
          className="btn btn-primary"
          onClick={() => doAction("cv")}
          disabled={!!busyAction}
        >
          {busyAction === "cv" ? "Génération…" : "Créer mon CV ciblé"}
        </button>
        <button
          className="btn btn-outline"
          onClick={() => doAction("letter")}
          disabled={!!busyAction}
        >
          {busyAction === "letter" ? "Génération…" : "Lettre de motivation"}
        </button>
        <button
          className="btn btn-outline"
          onClick={() => doAction("prep")}
          disabled={!!busyAction}
        >
          {busyAction === "prep" ? "Préparation…" : "Préparer l'entretien"}
        </button>
        <button
          className="btn btn-ghost"
          onClick={() => doAction("apply")}
          disabled={!!busyAction}
        >
          {busyAction === "apply" ? "…" : "Suivre ma candidature"}
        </button>
      </div>

      {templates && (
        <section className="panel">
          <div className="section-head">
            <h2>Choisissez votre modèle de CV</h2>
            <button className="btn btn-ghost btn-small" onClick={() => setTemplates(undefined)}>
              Fermer
            </button>
          </div>
          {templates.length === 0 && <p className="muted">Chargement…</p>}
          {templates.map((t) => (
            <div className="panel-light" key={t.id}>
              <div className="section-head">
                <h3 style={{ margin: 0 }}>{t.name}</h3>
                {t.ats_friendly && <span className="badge badge-strong">Compatible ATS</span>}
              </div>
              <p className="small muted">{t.description}</p>
              <button
                className="btn btn-primary btn-small"
                onClick={() => generateCv(t.id)}
                disabled={!!busyAction}
              >
                {busyAction === "cv" ? "Génération…" : `Générer en ${t.name}`}
              </button>
            </div>
          ))}
        </section>
      )}

      {prep && (
        <section className="match-block">
          <h2>Préparation d'entretien</h2>
          <h3>Pitch professionnel</h3>
          <p>{prep.pitch}</p>
          {prep.likely_questions.length > 0 && (
            <>
              <h3>Questions probables</h3>
              <ul className="explain-list">
                {prep.likely_questions.map((q, i) => <li key={i}>{q}</li>)}
              </ul>
            </>
          )}
          {prep.technical.length > 0 && (
            <>
              <h3>Questions techniques</h3>
              <ul className="explain-list">
                {prep.technical.map((q, i) => <li key={i}>{q}</li>)}
              </ul>
            </>
          )}
          {prep.behavioral.length > 0 && (
            <>
              <h3>Questions comportementales</h3>
              <ul className="explain-list">
                {prep.behavioral.map((q, i) => <li key={i}>{q}</li>)}
              </ul>
            </>
          )}
          {prep.prep_tips.length > 0 && (
            <>
              <h3>Conseils</h3>
              <ul className="explain-list">
                {prep.prep_tips.map((t, i) => <li key={i}>{t}</li>)}
              </ul>
            </>
          )}
        </section>
      )}
    </div>
  );
}
