import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import ProfileEditor from "../components/ProfileEditor.jsx";
import { sanitizeProfile } from "../lib.js";
import { ErrorNote, Loader } from "../components/ui.jsx";

// Validation humaine (§47) : le brouillon (import CV ou questionnaire)
// n'est enregistré qu'après vérification et clic sur « Valider mon profil ».
export default function DraftReview() {
  const navigate = useNavigate();
  const [draft, setDraft] = useState(null);
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const raw = sessionStorage.getItem("orientskill_draft");
    if (!raw) {
      navigate("/onboarding");
      return;
    }
    try {
      const d = JSON.parse(raw);
      setDraft(d.draft);
      setReport(d.report);
    } catch {
      sessionStorage.removeItem("orientskill_draft");
      navigate("/onboarding");
    }
  }, [navigate]);

  async function validate() {
    setBusy(true);
    setError("");
    try {
      await api("/profile", { method: "PUT", body: sanitizeProfile(draft) });
      sessionStorage.removeItem("orientskill_draft");
      navigate("/");
    } catch (err) {
      setError(err.detail);
      setBusy(false);
    }
  }

  if (!draft) {
    return <div className="page"><Loader /></div>;
  }

  return (
    <div className="page">
      <h1>Analyse terminée : vérifiez votre profil</h1>
      <p className="page-lead">
        Rien n'est enregistré pour l'instant. Corrigez ou complétez les
        informations ci-dessous, puis validez pour enregistrer votre profil
        professionnel.
      </p>

      <div className="report-chips">
        <span className="chip"><strong>{report?.skills_found ?? draft.skills.length}</strong> compétence(s) identifiée(s)</span>
        <span className="chip"><strong>{report?.experiences_found ?? draft.experiences.length}</strong> expérience(s)</span>
        <span className="chip"><strong>{report?.certifications_found ?? draft.certifications.length}</strong> certification(s)</span>
        <span className="chip"><strong>{report?.degrees_found ?? draft.education.length}</strong> formation(s)</span>
        {(report?.career_fields || []).length > 0 && (
          <span className="chip"><strong>{report.career_fields.length}</strong> domaine(s) professionnel(s) possible(s)</span>
        )}
      </div>

      <ErrorNote error={error} />

      <ProfileEditor profile={draft} onChange={setDraft} />

      <div className="actions-row">
        <button className="btn btn-primary" onClick={validate} disabled={busy}>
          {busy ? "Enregistrement…" : "Valider mon profil"}
        </button>
        <button
          className="btn btn-ghost"
          onClick={() => navigate("/onboarding")}
          disabled={busy}
        >
          Recommencer
        </button>
      </div>
    </div>
  );
}
