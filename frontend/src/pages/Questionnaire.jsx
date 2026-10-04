import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { Loader, ErrorNote } from "../components/ui.jsx";

// Diagnostic par questionnaire (§9ter, mode sans CV).
function QuestionField({ q, value, onChange }) {
  const id = `q-${q.id}`;
  if (q.type === "text") {
    return (
      <label className="field">
        <span>{q.label}</span>
        <input value={value || ""} onChange={(e) => onChange(e.target.value)} />
      </label>
    );
  }
  if (q.type === "textarea" || q.type === "list") {
    return (
      <label className="field">
        <span>{q.label}</span>
        <textarea
          rows={q.type === "list" ? 3 : 4}
          value={Array.isArray(value) ? value.join("\n") : value || ""}
          onChange={(e) =>
            onChange(q.type === "list"
              ? e.target.value.split("\n").map((s) => s.trim()).filter(Boolean)
              : e.target.value)
          }
        />
      </label>
    );
  }
  if (q.type === "choice") {
    return (
      <div className="field">
        <span>{q.label}</span>
        <div className="inline-fields">
          {(q.options || []).map((opt) => (
            <label key={opt} className="check">
              <input
                type="radio"
                name={id}
                checked={value === opt}
                onChange={() => onChange(opt)}
              />
              {opt}
            </label>
          ))}
        </div>
      </div>
    );
  }
  if (q.type === "multi_choice") {
    const arr = value || [];
    return (
      <div className="field">
        <span>{q.label}</span>
        <div className="inline-fields">
          {(q.options || []).map((opt) => (
            <label key={opt} className="check">
              <input
                type="checkbox"
                checked={arr.includes(opt)}
                onChange={(e) =>
                  onChange(e.target.checked
                    ? [...arr, opt]
                    : arr.filter((x) => x !== opt))
                }
              />
              {opt}
            </label>
          ))}
        </div>
      </div>
    );
  }
  return null;
}

// Niveau « sans diplôme » : on pose la question de débrouillardise à la
// place des questions académiques (filière, établissement, certifications).
const SANS_DIPLÔME = "Compétences acquises sur le terrain (sans diplôme)";

function StepQuestions({ step, answers, setAnswer }) {
  const level = answers["q_education_level"];
  const sansDiplome = step.id === "formation" && level === SANS_DIPLÔME;
  const questions = (step.questions || []).filter((q) => {
    if (step.id !== "formation") return true;
    if (sansDiplome) return q.id !== "q_field" && q.id !== "q_institution" && q.id !== "q_certifications";
    return q.id !== "q_domain";
  });
  return (
    <>
      {questions.map((q) => (
        <QuestionField
          key={q.id}
          q={q}
          value={answers[q.id]}
          onChange={(v) => setAnswer(q.id, v)}
        />
      ))}
      {sansDiplome && (
        <div className="alert alert-info">
          Parcours sans diplôme : votre expérience de terrain compte autant.
          Décrivez ce que vous savez faire, la plateforme en déduit vos
          compétences réelles.
        </div>
      )}
    </>
  );
}

export default function Questionnaire() {
  const navigate = useNavigate();
  const [steps, setSteps] = useState(null);
  const [answers, setAnswers] = useState({});
  const [stepIdx, setStepIdx] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/questionnaire")
      .then((d) => setSteps(d.steps))
      .catch((e) => setError(e.detail));
  }, []);

  if (error) {
    return <div className="page page-narrow"><ErrorNote error={error} /></div>;
  }
  if (!steps) {
    return <div className="page page-narrow"><Loader label="Chargement du questionnaire…" /></div>;
  }

  const step = steps[stepIdx];
  const setAnswer = (qid, value) => setAnswers((a) => ({ ...a, [qid]: value }));

  async function submit() {
    setBusy(true);
    setError("");
    try {
      const res = await api("/questionnaire/submit", {
        method: "POST",
        body: { answers },
      });
      sessionStorage.setItem("orientskill_draft", JSON.stringify(res));
      navigate("/validation-profil");
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  const lastIdx = steps.length - 1;

  return (
    <div className="page page-narrow">
      <h1>Créer mon profil</h1>
      <p className="page-lead">
        Étape {stepIdx + 1} sur {steps.length} · {step.title}
      </p>
      <div className="progress">
        <span style={{ width: `${((stepIdx + 1) / steps.length) * 100}%` }} />
      </div>
      <ErrorNote error={error} />
      <div className="panel">
        <h2>{step.title}</h2>
        <StepQuestions step={step} answers={answers} setAnswer={setAnswer} />
        <div className="actions-row">
          {stepIdx > 0 && (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setStepIdx(stepIdx - 1)}
            >
              Précédent
            </button>
          )}
          {stepIdx < lastIdx && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setStepIdx(stepIdx + 1)}
            >
              Suivant
            </button>
          )}
          {stepIdx === lastIdx && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={submit}
              disabled={busy}
            >
              {busy ? "Analyse…" : "Générer mon profil"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
