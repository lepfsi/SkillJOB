import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";

// Première connexion (§58) : Importer mon CV ou Créer mon profil.
// L'analyse produit un brouillon : la validation humaine se fait
// ensuite sur la page DraftReview (§47).
export default function Onboarding() {
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submitCv(e) {
    e.preventDefault();
    setError("");
    if (!text.trim() && !file) {
      setError("Collez le texte de votre CV ou choisissez un fichier PDF / TXT.");
      return;
    }
    setBusy(true);
    try {
      let res;
      if (file) {
        const form = new FormData();
        form.append("file", file);
        res = await api("/profile/import-cv", { method: "POST", form });
      } else {
        res = await api("/profile/import-cv", { method: "POST", body: { text } });
      }
      sessionStorage.setItem("orientskill_draft", JSON.stringify(res));
      navigate("/validation-profil");
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <h1>Bienvenue. Construisons votre profil professionnel.</h1>
      <p className="page-lead">
        Votre profil est la source de vérité de la plateforme : il alimente
        l'orientation, le matching avec les offres et la génération de vos
        documents de candidature.
      </p>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="onboarding-grid">
        <form className="panel" onSubmit={submitCv}>
          <h2>Importer mon CV</h2>
          <p className="muted small">
            Collez le contenu de votre CV ci-dessous, ou téléversez un fichier
            PDF ou TXT. L'IA extrait vos formations, expériences, compétences
            et certifications.
          </p>
          <textarea
            rows="9"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={"Collez ici le texte de votre CV…\n\nExemple :\nTechnicien support IT, 2021 à 2023\nMaintenance de postes, administration Windows Server…"}
          />
          <label className="field">
            <span>Ou choisir un fichier (PDF / TXT)</span>
            <input
              type="file"
              accept=".pdf,.txt"
              onChange={(e) => setFile(e.target.files[0] || null)}
            />
          </label>
          {file && (
            <p className="small muted">
              Fichier sélectionné : {file.name}
              {" "}
              <button
                type="button"
                className="btn btn-ghost btn-small"
                onClick={() => setFile(null)}
              >
                Retirer
              </button>
            </p>
          )}
          <div className="actions-row">
            <button className="btn btn-primary" disabled={busy}>
              {busy ? "Analyse en cours…" : "Analyser mon CV"}
            </button>
          </div>
        </form>

        <div className="panel">
          <h2>Je n'ai pas de CV</h2>
          <p className="muted small">
            Aucun problème. Répondez à un questionnaire intelligent : quelques
            questions simples sur vos études, vos expériences, y compris les
            petits boulots, missions et bénévolats, puis vos compétences.
          </p>
          <div className="actions-row">
            <button
              className="btn btn-outline"
              onClick={() => navigate("/questionnaire")}
            >
              Créer mon profil
            </button>
          </div>
          <p className="small muted">
            L'absence d'expérience formelle n'est pas une absence de compétence.
          </p>
        </div>
      </div>
    </div>
  );
}
