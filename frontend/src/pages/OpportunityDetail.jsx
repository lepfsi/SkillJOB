import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, apiRaw } from "../api/client.js";
import MatchBadge from "../components/MatchBadge.jsx";
import ScoreBar from "../components/ScoreBar.jsx";
import SkillTag from "../components/SkillTag.jsx";
import Ring from "../components/Ring.jsx";
import { Icon, I, ArrowIcon } from "../components/icons.jsx";
import TemplateThumb from "../components/TemplateThumb.jsx";
import AccentRow from "../components/AccentRow.jsx";
import PreviewImage from "../components/PreviewImage.jsx";
import AgentSideCard from "../components/AgentSideCard.jsx";
import JobVisual from "../components/JobVisual.jsx";
import { templateAccentHex, fmtDate, initialsOf, plural, scoreLevel, LEVEL_LABELS } from "../lib.js";
import { Loader, ErrorNote } from "../components/ui.jsx";

// Détail d'une offre (§30) : description, profil recherché, compétences
// requises et correspondance explicable (✓ couverte / △ partielle /
// ○ manquante). Toutes les actions disponibles sur l'offre sont regroupées
// dans une colonne latérale, et la source de l'offre reste toujours
// affichée (§51). Aucune donnée n'est inventée (§47).

function publishedLabel(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (days <= 0) return "Publiée aujourd'hui";
  if (days === 1) return "Publiée hier";
  if (days < 30) return `Publiée il y a ${days} jours`;
  return `Publiée le ${fmtDate(iso)}`;
}

const REPORT_REASONS = [
  { id: "arnaque", label: "Offre frauduleuse ou demande d'argent" },
  { id: "contenu_trompeur", label: "Contenu trompeur ou incohérent" },
  { id: "offre_expiree", label: "Offre expirée ou déjà pourvue" },
  { id: "discrimination", label: "Discrimination ou propos inapproprié" },
  { id: "doublon", label: "Doublon d'une autre offre" },
  { id: "autre", label: "Autre problème" },
];

// Teintes de score : fortes en vert, moyennes en orange, faibles en gris.
function scoreClass(score) {
  const level = scoreLevel(score);
  if (level === "forte") return "strong";
  if (level === "moyenne") return "medium";
  return "weak";
}

// Choix de la couleur d'accent et aperçus : composants partagés.

export default function OpportunityDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null); // { job, match }
  const [allJobs, setAllJobs] = useState([]);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const [prep, setPrep] = useState(null);
  const [templates, setTemplates] = useState(undefined); // undefined = fermé, null = chargement
  const [letterTemplates, setLetterTemplates] = useState(undefined);
  const [accent, setAccent] = useState(""); // "" = couleur du modèle
  const [reportOpen, setReportOpen] = useState(false);
  const [reportForm, setReportForm] = useState({ reason: "", details: "" });
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState("");
  const [reportFlash, setReportFlash] = useState("");
  // Soumission de candidature : modale + documents + note
  const [submitOpen, setSubmitOpen] = useState(false);
  const [myDocs, setMyDocs] = useState(null); // null = chargement
  const [submitForm, setSubmitForm] = useState({ cv_id: "", letter_id: "", note: "" });
  const [submitBusy, setSubmitBusy] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [submitFlash, setSubmitFlash] = useState("");
  const [myApplication, setMyApplication] = useState(null);
  const [searchParams] = useSearchParams();

  // Lien profond : /opportunites/:id?galerie=cv (ou lettre) ouvre
  // directement le sélecteur de modèles, partageable tel quel.
  useEffect(() => {
    const galerie = searchParams.get("galerie");
    if (galerie === "cv" || galerie === "lettre") {
      doAction(galerie);
    }
    // au montage uniquement
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Un panneau qui s'ouvre se MONTRE : défilement doux vers lui,
  // jamais de section cachée « en bas de page ».
  const galleryRef = useRef(null);
  const letterPanelRef = useRef(null);
  useEffect(() => {
    if (templates !== undefined && galleryRef.current) {
      galleryRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [templates]);
  useEffect(() => {
    if (letterTemplates !== undefined && letterPanelRef.current) {
      letterPanelRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [letterTemplates]);

  useEffect(() => {
    api(`/jobs/${id}`)
      .then(setData)
      .catch((e) => setError(e.detail));
    api("/applications")
      .then((apps) => setMyApplication(
        (apps || []).find((a) => a.job_id === Number(id)) || null
      ))
      .catch(() => setMyApplication(null));
  }, [id]);

  // Offres proches : liste réelle, filtrée sur le secteur de l'offre courante.
  useEffect(() => {
    api("/jobs?limit=200")
      .then((list) => setAllJobs(Array.isArray(list) ? list : []))
      .catch(() => setAllJobs([]));
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
        setLetterTemplates(null);
        const list = await api("/letter-templates");
        setLetterTemplates(list);
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

  // ---- Soumission de candidature : ouvrir la modale avec les documents
  async function openSubmitModal() {
    setSubmitError("");
    setSubmitFlash("");
    setSubmitOpen(true);
    if (myDocs === null) {
      try {
        const docs = await api("/documents");
        // CVs ciblés pour cette offre d'abord, puis généralistes, puis lettres
        const cvs = docs.filter((d) => d.kind === "cv");
        const letters = docs.filter((d) => d.kind === "cover_letter");
        const targetedCv = cvs.find((d) => d.job_id === Number(id)) || null;
        const generalCv = cvs.find((d) => !d.job_id) || null;
        const targetedLetter = letters.find((d) => d.job_id === Number(id)) || null;
        setMyDocs({ cvs, letters, targetedCv, generalCv, targetedLetter });
        setSubmitForm((f) => ({
          ...f,
          cv_id: targetedCv ? String(targetedCv.id) : (generalCv ? String(generalCv.id) : ""),
          letter_id: targetedLetter ? String(targetedLetter.id) : "",
        }));
      } catch (err) {
        setMyDocs({ cvs: [], letters: [], targetedCv: null, generalCv: null, targetedLetter: null });
        setSubmitError(err.detail);
      }
    }
  }

  async function submitCandidature(event) {
    event.preventDefault();
    setSubmitError("");
    if (!submitForm.cv_id) {
      setSubmitError("Choisissez le CV à envoyer.");
      return;
    }
    setSubmitBusy(true);
    try {
      const body = {
        cv_document_id: Number(submitForm.cv_id),
        cover_note: submitForm.note.trim(),
      };
      if (submitForm.letter_id) {
        body.cover_letter_document_id = Number(submitForm.letter_id);
      }
      await api(`/applications/jobs/${id}/submit`, { method: "POST", body });
      setSubmitOpen(false);
      setSubmitFlash(
        "Candidature envoyée. Le recruteur a été notifié, vous pouvez suivre la réponse depuis vos candidatures."
      );
    } catch (err) {
      setSubmitError(err.detail);
    } finally {
      setSubmitBusy(false);
    }
  }

  // Modèle + accent choisis par le candidat : le contenu reste celui du
  // profil validé (§47), seule la mise en page change. Le PDF part tout
  // de suite en téléchargement, puis le document s'ouvre en tête de page.
  async function generateCv(templateId) {
    setBusyAction("cv");
    setActionError("");
    try {
      const doc = await api(`/jobs/${id}/cv`, {
        method: "POST",
        body: { template: templateId, accent: accent || null },
      });
      await downloadDocument(doc.id, "CV");
      navigate(`/documents?open=${doc.id}`);
    } catch (err) {
      setActionError(err.detail);
      setBusyAction("");
    }
  }

  async function generateLetter(templateId) {
    setBusyAction("letter");
    setActionError("");
    try {
      const doc = await api(`/jobs/${id}/cover-letter`, {
        method: "POST",
        body: { template: templateId, accent: accent || null },
      });
      await downloadDocument(doc.id, "Lettre");
      navigate(`/documents?open=${doc.id}`);
    } catch (err) {
      setActionError(err.detail);
      setBusyAction("");
    }
  }

  // Téléchargement immédiat du PDF généré (l'utilisateur voit le résultat
  // sans chercher : rien n'apparaît « en bas de page »).
  async function downloadDocument(docId, prefix) {
    try {
      const res = await apiRaw(`/documents/${docId}/export?format=pdf`);
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${prefix}-${docId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      /* le téléchargement est un confort : la navigation continue */
    }
  }

  async function submitReport(event) {
    event.preventDefault();
    setReportError("");
    if (!reportForm.reason) {
      setReportError("Choisissez le motif du signalement.");
      return;
    }
    setReportBusy(true);
    try {
      const report = await api(`/jobs/${id}/reports`, {
        method: "POST",
        body: {
          reason: reportForm.reason,
          details: reportForm.details.trim(),
        },
      });
      setData((prev) => ({ ...prev, my_report: report }));
      setReportOpen(false);
      setReportForm({ reason: "", details: "" });
      setReportFlash("Signalement transmis. Il sera examiné par l'administration.");
    } catch (err) {
      if (err.status === 409) {
        try {
          const fresh = await api(`/jobs/${id}`);
          setData(fresh);
          setReportOpen(false);
        } catch {
          /* le message reste affiché */
        }
      }
      setReportError(err.detail);
    } finally {
      setReportBusy(false);
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
  const myReport = data.my_report;
  const company = job.company_branding;
  const level = match ? scoreLevel(match.score) : null;
  const totalSkills = match
    ? match.covered.length + match.partial.length + match.missing.length
    : 0;

  const sameSector = allJobs
    .filter((j) => j.id !== job.id && j.sector === job.sector)
    .sort((a, b) => (b.match_score ?? -1) - (a.match_score ?? -1))
    .slice(0, 4);

  return (
    <div className="page offre-page">
      <Link to="/opportunites" className="offre-back">← Retour aux opportunités</Link>

      {reportFlash && <div className="alert alert-success">{reportFlash}</div>}
      {submitFlash && <div className="alert alert-success">{submitFlash}</div>}

      {/* Photo facultative, sinon visuel par défaut inspiré du domaine. */}
      <JobVisual job={job} variant="banner" className="opp-detail-visual" />

      {/* ---------- Bandeau de l'offre ---------- */}
      <section className="offre-hero">
        <div className="offre-hero-main">
          <span className="offre-eyebrow">
            Offre d'emploi{job.sector ? ` · ${job.sector}` : ""}
          </span>
          <h1>{job.title}</h1>
          <div className="offre-hero-meta">
            <span><Icon d={I.briefcase} size={14} /> {job.company}</span>
            <span><Icon d={I.pin} size={14} /> {job.location}</span>
            <span><Icon d={I.clipboard} size={14} /> {job.contract_type}</span>
            {job.salary && <span><Icon d={I.award} size={14} /> {job.salary}</span>}
            <span><Icon d={I.clock} size={14} /> {publishedLabel(job.published_at)}</span>
          </div>
          <p className="offre-hero-source">
            Source :{" "}
            <a href={job.source.url} target="_blank" rel="noreferrer">{job.source.name}</a>
            {job.deadline ? ` · Candidatures jusqu'au ${fmtDate(job.deadline)}` : ""}
          </p>
        </div>

        <div className="offre-score">
          {match ? (
            <>
              <div className="offre-score-top">
                <Ring score={match.score} text={`${match.score}/100`} />
                <div className="offre-score-body">
                  <span className="offre-score-label">Correspondance</span>
                  <strong>{LEVEL_LABELS[level]}</strong>
                  <span className="small muted">
                    {match.covered.length} sur {totalSkills} compétence{plural(totalSkills, "", "s")} couverte
                    {plural(match.covered.length, "", "s")}
                  </span>
                </div>
              </div>
              <span className="offre-score-note">
                {match.missing.length + match.partial.length > 0
                  ? `${match.missing.length + match.partial.length} compétence${plural(match.missing.length + match.partial.length, "", "s")} à renforcer pour cette offre.`
                  : "Toutes les compétences requises sont couvertes."}
              </span>
            </>
          ) : (
            <>
              <MatchBadge score={null} />
              <p className="small muted" style={{ margin: "0.6rem 0 0" }}>
                Complétez votre profil pour obtenir votre correspondance avec cette offre.
              </p>
              <Link className="btn btn-primary btn-small" to="/onboarding">
                Construire mon profil <ArrowIcon direction="right" size={12} />
              </Link>
            </>
          )}
        </div>
      </section>

      <div className="dash-columns">
        <div className="dash-col-main">
          {/* ---------- Description ---------- */}
          <section className="dash-card">
            <div className="dash-card-head"><h2>Description de l'offre</h2></div>
            {(job.description || "").split("\n").filter(Boolean).map((p, i) => (
              <p className="offre-text" key={i}>{p}</p>
            ))}
            {job.requirements && (
              <>
                <h3 className="offre-subtitle">Profil recherché</h3>
                {job.requirements.split("\n").filter(Boolean).map((p, i) => (
                  <p className="offre-text" key={i}>{p}</p>
                ))}
              </>
            )}
          </section>

          {/* ---------- Compétences requises ---------- */}
          <section className="dash-card">
            <div className="dash-card-head">
              <h2>Compétences requises</h2>
              <span className="small muted">
                {job.required_skills.length} compétence{plural(job.required_skills.length, "", "s")}
              </span>
            </div>
            <p className="small muted" style={{ marginTop: 0 }}>
              « essentielle » = exigée par l'offre · « appréciée » = un atout supplémentaire.
            </p>
            <div className="chip-row">
              {job.required_skills.length > 0 ? (
                job.required_skills.map((rs) => (
                  <SkillTag key={rs.name} name={rs.name} state="neutral" importance={rs.importance} />
                ))
              ) : (
                <p className="small muted" style={{ margin: 0 }}>
                  Aucune compétence n'a été détaillée par l'employeur.
                </p>
              )}
            </div>
          </section>

          {/* ---------- Correspondance explicable ---------- */}
          {match ? (
            <section className="offre-match">
              <div className="offre-match-head">
                <Icon d={I.target} size={17} />
                <h2>Votre correspondance avec cette offre</h2>
              </div>

              <ScoreBar
                score={match.score}
                covered={match.covered.length}
                partial={match.partial.length}
                missing={match.missing.length}
              />

              <div className="offre-match-grid">
                <div className="offre-panel">
                  <h3><span className="mk mk-ok">✓</span> Compétences couvertes</h3>
                  {match.covered.length > 0 ? (
                    <ul className="offre-marks">
                      {match.covered.map((s) => (
                        <li key={s}><span className="mk mk-ok">✓</span>{s}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="small muted">Aucune compétence couverte pour l'instant.</p>
                  )}
                </div>

                <div className="offre-panel">
                  <h3><span className="mk mk-part">△</span> Compétences partielles</h3>
                  {match.partial.length > 0 ? (
                    <ul className="offre-marks">
                      {match.partial.map((s) => (
                        <li key={s}><span className="mk mk-part">△</span>{s}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="small muted">Aucune compétence partiellement couverte.</p>
                  )}
                </div>

                <div className="offre-panel">
                  <h3><span className="mk mk-miss">○</span> Compétences manquantes</h3>
                  {match.missing.length > 0 ? (
                    <ul className="offre-marks">
                      {match.missing.map((s) => (
                        <li key={s}><span className="mk mk-miss">○</span>{s}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="small muted">Aucune compétence manquante : dossier complet.</p>
                  )}
                </div>
              </div>

              <div className="offre-explain">
                <h3 className="offre-subtitle">Pourquoi cette offre vous correspond</h3>
                <p className="offre-text">{match.explanation}</p>

                {match.strengths.length > 0 && (
                  <>
                    <h3 className="offre-subtitle">Vos points forts pour cette offre</h3>
                    <ul className="offre-marks offre-strengths">
                      {match.strengths.map((s, i) => (
                        <li key={i}><span className="mk mk-ok">✓</span>{s}</li>
                      ))}
                    </ul>
                  </>
                )}

                {match.recommended_actions.length > 0 && (
                  <>
                    <h3 className="offre-subtitle">Ce que vous pouvez améliorer</h3>
                    <ul className="explain-list">
                      {match.recommended_actions.map((a, i) => <li key={i}>{a}</li>)}
                    </ul>
                  </>
                )}
              </div>

              {(match.missing.length > 0 || match.partial.length > 0) && (
                <div className="offre-tip">
                  <Icon d={I.zap} size={16} />
                  <span>
                    {match.missing.length > 0
                      ? `Il vous manque ${match.missing.length} compétence${plural(match.missing.length, "", "s")} pour cette offre`
                      : `${match.partial.length} compétence${plural(match.partial.length, "", "s")} à consolider pour cette offre`}
                    {" "}
                    ({[...match.missing, ...match.partial].slice(0, 3).join(", ")}
                    {match.missing.length + match.partial.length > 3 ? "…" : ""}).
                  </span>
                  <Link className="btn btn-outline btn-small" to="/learning">
                    Voir les formations <ArrowIcon direction="right" size={12} />
                  </Link>
                </div>
              )}
            </section>
          ) : (
            <section className="dash-card">
              <div className="alert alert-info" style={{ margin: 0 }}>
                Complétez votre profil pour obtenir une analyse de correspondance
                détaillée avec cette offre.{" "}
                <Link to="/onboarding">Construire mon profil →</Link>
              </div>
            </section>
          )}

          {/* ---------- Modèles de CV (génération ciblée, §47) ---------- */}
          {templates !== undefined && (
            <section className="dash-card" ref={galleryRef}>
              <div className="dash-card-head">
                <h2>Choisissez votre modèle de CV</h2>
                <button className="btn btn-ghost btn-small" onClick={() => setTemplates(undefined)}>
                  Fermer
                </button>
              </div>
              <p className="small muted" style={{ marginTop: 0 }}>
                Le CV ciblé reprend uniquement les informations de votre profil
                validé (§47) : le modèle change la mise en page, jamais les faits.
                {" "}Besoin des bons mots ?{" "}
                <Link to={`/assistant?q=${encodeURIComponent(`Adapte mon CV pour l'offre « ${job.title} »`)}`}>
                  Ori vous propose les textes d'adaptation
                </Link>.
              </p>
              {templates === null ? (
                <p className="small muted" style={{ margin: 0 }}>Chargement des modèles…</p>
              ) : templates.length === 0 ? (
                <p className="small muted" style={{ margin: 0 }}>Aucun modèle disponible.</p>
              ) : (
                <>
                  <AccentRow accent={accent} onPick={setAccent} />
                  <div className="tpl-grid">
                    {templates.map((t) => (
                      <div className="tpl-card" key={t.id}>
                        <div className="tpl-thumb-row">
                          <PreviewImage
                            src={`/templates/cv-${t.id}.png`}
                            alt="Aperçu du modèle (rendu PDF réel, données d'exemple)"
                            className="tpl-preview"
                            fallback={<TemplateThumb template={t} accent={accent} />}
                          />
                          <div className="tpl-card-main">
                            <div className="tpl-card-head">
                              <h3>{t.name}</h3>
                              {t.ats_friendly && (
                                <span className="badge badge-strong">Compatible ATS</span>
                              )}
                            </div>
                            <p className="small muted">{t.description}</p>
                          </div>
                        </div>
                        <button
                          className="btn btn-primary btn-small"
                          onClick={() => generateCv(t.id)}
                          disabled={!!busyAction}
                        >
                          {busyAction === "cv" ? "Génération…" : "Générer"}
                        </button>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </section>
          )}

          {/* ---------- Modèles de lettre (même contenu, autre mise en page) ---------- */}
          {letterTemplates !== undefined && (
            <section className="dash-card" ref={letterPanelRef}>
              <div className="dash-card-head">
                <h2>Choisissez votre modèle de lettre</h2>
                <button className="btn btn-ghost btn-small" onClick={() => setLetterTemplates(undefined)}>
                  Fermer
                </button>
              </div>
              <p className="small muted" style={{ marginTop: 0 }}>
                Mêmes faits issus de votre profil, autre mise en page (§17) :
                « Courriel » est prêt à coller dans un e-mail de candidature.
                {" "}Ori peut aussi{" "}
                <Link to={`/assistant?q=${encodeURIComponent(`Adapte ma lettre pour l'offre « ${job.title} »`)}`}>
                  vous proposer les textes de la lettre
                </Link>.
              </p>
              {letterTemplates === null ? (
                <p className="small muted" style={{ margin: 0 }}>Chargement des modèles…</p>
              ) : letterTemplates.length === 0 ? (
                <p className="small muted" style={{ margin: 0 }}>Aucun modèle disponible.</p>
              ) : (
                <>
                  <AccentRow accent={accent} onPick={setAccent} />
                  <div className="tpl-grid">
                    {letterTemplates.map((t) => (
                      <div className="tpl-card" key={t.id}>
                        <div className="tpl-thumb-row">
                          <PreviewImage
                            src={`/templates/lettre-${t.id}.png`}
                            alt="Aperçu de la lettre (rendu PDF réel, données d'exemple)"
                            className="tpl-preview"
                            fallback={
                              <TemplateThumb
                                template={{ id: t.id === "email" ? "" : "classique", columns: 1 }}
                                accent={accent}
                                flat={t.id === "email"}
                              />
                            }
                          />
                          <div className="tpl-card-main">
                            <div className="tpl-card-head">
                              <h3>{t.name}</h3>
                            </div>
                            <p className="small muted">{t.description}</p>
                          </div>
                        </div>
                        <button
                          className="btn btn-primary btn-small"
                          onClick={() => generateLetter(t.id)}
                          disabled={!!busyAction}
                        >
                          {busyAction === "letter" ? "Génération…" : "Générer"}
                        </button>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </section>
          )}

          {prep && (
            <section className="dash-card">
              <div className="dash-card-head">
                <h2>Préparation d'entretien</h2>
                <button className="btn btn-ghost btn-small" onClick={() => setPrep(null)}>
                  Fermer
                </button>
              </div>
              <h3 className="offre-subtitle">Pitch professionnel</h3>
              <p className="offre-text">{prep.pitch}</p>
              {prep.likely_questions.length > 0 && (
                <>
                  <h3 className="offre-subtitle">Questions probables</h3>
                  <ul className="explain-list">
                    {prep.likely_questions.map((q, i) => <li key={i}>{q}</li>)}
                  </ul>
                </>
              )}
              {prep.technical.length > 0 && (
                <>
                  <h3 className="offre-subtitle">Questions techniques</h3>
                  <ul className="explain-list">
                    {prep.technical.map((q, i) => <li key={i}>{q}</li>)}
                  </ul>
                </>
              )}
              {prep.behavioral.length > 0 && (
                <>
                  <h3 className="offre-subtitle">Questions comportementales</h3>
                  <ul className="explain-list">
                    {prep.behavioral.map((q, i) => <li key={i}>{q}</li>)}
                  </ul>
                </>
              )}
              {prep.prep_tips.length > 0 && (
                <>
                  <h3 className="offre-subtitle">Conseils</h3>
                  <ul className="explain-list">
                    {prep.prep_tips.map((t, i) => <li key={i}>{t}</li>)}
                  </ul>
                </>
              )}
            </section>
          )}

          {/* ---------- Offres proches ---------- */}
          {sameSector.length > 0 && (
            <section className="dash-card">
              <div className="dash-card-head">
                <h2>Offres proches dans le même secteur</h2>
                <Link className="link-more" to="/opportunites">
                  Voir toutes les offres <ArrowIcon direction="right" />
                </Link>
              </div>
              <div className="offre-sim">
                {sameSector.map((j) => (
                  <Link className="opps-row" to={`/opportunites/${j.id}`} key={j.id}>
                    <JobVisual job={j} variant="row" />
                    <span className="opps-row-main">
                      <span className="opps-row-top">
                        <strong>{j.title}</strong>
                        {j.match_score != null && (
                          <span className={`opps-score opps-score-${scoreClass(j.match_score)}`}>
                            {j.match_score}/100
                          </span>
                        )}
                      </span>
                      <span className="opps-row-meta">
                        <span><Icon d={I.briefcase} size={12} /> {j.company}</span>
                        <span><Icon d={I.pin} size={12} /> {j.location}</span>
                        <span>{j.contract_type}</span>
                      </span>
                    </span>
                  </Link>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* ---------- Colonne latérale ---------- */}
        <div className="dash-col-side">
          <section className="dash-card offre-actions">
            <div className="dash-card-head"><h2>Passer à l'action</h2></div>
            <p className="small muted" style={{ marginTop: 0 }}>
              Tout est généré à partir de votre profil validé : aucun contenu inventé.
            </p>

            <button
              className="btn btn-primary offre-action-btn"
              onClick={() => doAction("cv")}
              disabled={!!busyAction}
            >
              <Icon d={I.file} size={15} />
              {busyAction === "cv" ? "Génération…" : "Créer mon CV ciblé"}
            </button>
            <button
              className="btn btn-outline offre-action-btn"
              onClick={() => doAction("letter")}
              disabled={!!busyAction}
            >
              <Icon d={I.pen} size={15} />
              {busyAction === "letter" ? "Génération…" : "Lettre de motivation"}
            </button>

            {!myApplication?.submitted_at && (
              <button
                className="btn btn-primary offre-action-btn offre-submit-btn"
                onClick={openSubmitModal}
              >
                <Icon d={I.send} size={15} />
                Soumettre ma candidature
              </button>
            )}
            {myApplication?.submitted_at && (
              <span className="offre-submitted-badge">
                <Icon d={I.check} size={14} /> Candidature envoyée
              </span>
            )}

            <button
              className="btn btn-outline offre-action-btn"
              onClick={() => doAction("prep")}
              disabled={!!busyAction}
            >
              <Icon d={I.book} size={15} />
              {busyAction === "prep" ? "Préparation…" : "Préparer l'entretien"}
            </button>
            <button
              className="btn btn-ghost offre-action-btn"
              onClick={() => doAction("apply")}
              disabled={!!busyAction}
            >
              <Icon d={I.clipboard} size={15} />
              {busyAction === "apply" ? "Enregistrement…" : "Suivre ma candidature"}
            </button>

            <ErrorNote error={actionError} />
            {actionError && actionError.includes("Profil requis") && (
              <Link to="/onboarding" className="btn btn-primary btn-small">
                Construire mon profil
              </Link>
            )}

            <div className="offre-report-zone">
              {myReport ? (
                <span className={`report-status report-status-${myReport.status}`}>
                  Offre signalée
                </span>
              ) : (
                <button
                  type="button"
                  className="btn btn-ghost offre-action-btn"
                  onClick={() => {
                    setReportError("");
                    setReportOpen(true);
                  }}
                >
                  Signaler cette offre
                </button>
              )}
            </div>
          </section>

          {company && (
            <section className="dash-card">
              <div className="dash-card-head"><h2>L'entreprise</h2></div>
              <div className="offre-company">
                <span className="offre-company-logo">{initialsOf(company.name)}</span>
                <div>
                  <strong>{company.name}</strong>
                  {company.sector && <span className="small muted">{company.sector}</span>}
                </div>
              </div>
              {company.description && (
                <p className="small muted" style={{ margin: "0.6rem 0 0" }}>
                  {company.description}
                </p>
              )}
            </section>
          )}

          <section className="dash-card">
            <div className="dash-card-head"><h2>Traçabilité de l'offre</h2></div>
            <ul className="offre-trace">
              <li>
                <span>Source</span>
                <a href={job.source.url} target="_blank" rel="noreferrer">{job.source.name}</a>
              </li>
              <li>
                <span>Publication</span>
                <strong>{fmtDate(job.published_at)}</strong>
              </li>
              {job.deadline && (
                <li>
                  <span>Clôture</span>
                  <strong>{fmtDate(job.deadline)}</strong>
                </li>
              )}
              <li>
                <span>Secteur</span>
                <strong>{job.sector}</strong>
              </li>
              <li>
                <span>Contrat</span>
                <strong>{job.contract_type}</strong>
              </li>
            </ul>
          </section>

          <AgentSideCard
            page="Offres"
            hint="Ori peut analyser cette offre avec vous et préparer une candidature qui tient debout."
          />
        </div>
      </div>

      {reportOpen && (
        <div
          className="modal-backdrop"
          role="presentation"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget && !reportBusy) setReportOpen(false);
          }}
        >
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="report-title">
            <form onSubmit={submitReport}>
              <div className="modal-head">
                <h2 id="report-title">Signaler cette offre</h2>
                <button
                  type="button"
                  className="btn btn-ghost btn-small"
                  onClick={() => setReportOpen(false)}
                  disabled={reportBusy}
                >
                  Fermer
                </button>
              </div>
              <p className="small muted">
                Votre signalement sera transmis à l'administration pour vérification.
                Il ne modifie pas votre candidature.
              </p>
              <label className="field">
                <span>Motif *</span>
                <select
                  value={reportForm.reason}
                  onChange={(e) => setReportForm((f) => ({ ...f, reason: e.target.value }))}
                  required
                >
                  <option value="">Choisir un motif</option>
                  {REPORT_REASONS.map((reason) => (
                    <option key={reason.id} value={reason.id}>{reason.label}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Précisions {reportForm.reason === "autre" ? "*" : "(facultatif)"}</span>
                <textarea
                  rows="4"
                  value={reportForm.details}
                  onChange={(e) => setReportForm((f) => ({ ...f, details: e.target.value }))}
                  placeholder="Ce qui vous semble problématique dans cette offre."
                  required={reportForm.reason === "autre"}
                />
              </label>
              <ErrorNote error={reportError} />
              <div className="actions-row">
                <button className="btn btn-primary" disabled={reportBusy}>
                  {reportBusy ? "Envoi…" : "Envoyer le signalement"}
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => setReportOpen(false)}
                  disabled={reportBusy}
                >
                  Annuler
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {submitOpen && (
        <div
          className="modal-backdrop"
          role="presentation"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget && !submitBusy) setSubmitOpen(false);
          }}
        >
          <div className="modal modal-submit" role="dialog" aria-modal="true" aria-labelledby="submit-title">
            <form onSubmit={submitCandidature}>
              <div className="modal-head">
                <h2 id="submit-title">Soumettre ma candidature</h2>
                <button
                  type="button"
                  className="btn btn-ghost btn-small"
                  onClick={() => setSubmitOpen(false)}
                  disabled={submitBusy}
                >
                  Fermer
                </button>
              </div>
              <p className="small muted">
                Votre CV et votre lettre sont transmis au recruteur depuis votre
                bibliothèque OrientSkill AI. Pour une offre externe, OrientSkill
                AI transmet elle-même votre candidature par e-mail au publieur
                (CV et lettre en PDF, réponse adressée à votre adresse) quand
                son adresse de candidature est connue ; sinon, la date d'envoi
                est enregistrée et les instructions du publieur vous sont
                rappelées.
              </p>

              {myDocs === null ? (
                <p className="small muted">Chargement de vos documents…</p>
              ) : myDocs.cvs.length === 0 ? (
                <div className="alert alert-warn small">
                  Vous n'avez pas encore de CV. Générez d'abord votre CV ciblé
                  pour cette offre, puis revenez soumettre.
                </div>
              ) : (
                <>
                  <label className="field">
                    <span>CV à envoyer *</span>
                    <select
                      value={submitForm.cv_id}
                      onChange={(e) => setSubmitForm((f) => ({ ...f, cv_id: e.target.value }))}
                      required
                    >
                      <option value="">Choisir un CV</option>
                      {myDocs.cvs.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.job_id === Number(id) ? "CV ciblé · " : "CV généraliste · "}
                          {d.title}
                        </option>
                      ))}
                    </select>
                  </label>

                  {myDocs.letters.length > 0 && (
                    <label className="field">
                      <span>Lettre de motivation (facultative)</span>
                      <select
                        value={submitForm.letter_id}
                        onChange={(e) => setSubmitForm((f) => ({ ...f, letter_id: e.target.value }))}
                      >
                        <option value="">Sans lettre</option>
                        {myDocs.letters.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.job_id === Number(id) ? "Lettre ciblée · " : "Lettre généraliste · "}
                            {d.title}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}

                  <label className="field">
                    <span>Message au recruteur (facultatif)</span>
                    <textarea
                      rows="3"
                      value={submitForm.note}
                      onChange={(e) => setSubmitForm((f) => ({ ...f, note: e.target.value }))}
                      placeholder="Une phrase courte pour vous présenter (disponibilité, motivation)."
                      maxLength="2000"
                    />
                  </label>
                </>
              )}

              <ErrorNote error={submitError} />
              <div className="actions-row">
                <button
                  className="btn btn-primary"
                  disabled={submitBusy || !submitForm.cv_id}
                >
                  {submitBusy ? "Envoi de la candidature…" : "Envoyer ma candidature"}
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => setSubmitOpen(false)}
                  disabled={submitBusy}
                >
                  Annuler
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
