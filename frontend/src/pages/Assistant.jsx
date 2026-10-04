import { useEffect, useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { api } from "../api/client.js";
import { mapInternalPath, mdToHtml } from "../lib.js";

// Assistant conversationnel : Ori parle naturellement, rend le markdown
// (gras, listes, LIENS CLIQUABLES) et propose des ACTIONS réelles :
// générer le CV, rédiger la lettre, simuler l'entretien, construire le
// profil. L'utilisateur garde toujours le contrôle : chaque action est
// un bouton qu'il clique, et tout contenu généré passe par la validation.

const OPENINGS = [
  "Salut ! Moi c'est Ori. Une offre à analyser, un entretien à préparer, une compétence à monter ? Dis-moi tout.",
  "Bonjour ! Prêt à avancer aujourd'hui ? Pose ta question, ou colle le lien d'une offre qui t'intéresse.",
  "Salut ! Besoin d'un coup de main : métiers, formations, CV, entretien ? Je m'occupe du reste.",
  "Bonjour ! Par quoi on commence : explorer des opportunités, monter en compétences, ou préparer une candidature ?",
];

function ActionButtons({ actions, onExecuted }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function execute(action) {
    setBusy(action.type);
    setError("");
    try {
      if (action.type === "generate_cv") {
        const doc = await api(`/jobs/${action.job_id}/cv`, {
          method: "POST",
          body: { template: "classique" },
        });
        navigate(`/documents?open=${doc.id}`);
      } else if (action.type === "generate_letter") {
        const doc = await api(`/jobs/${action.job_id}/cover-letter`, { method: "POST" });
        navigate(`/documents?open=${doc.id}`);
      } else if (action.type === "interview_prep") {
        const prep = await api(`/jobs/${action.job_id}/interview-prep`, { method: "POST" });
        onExecuted(buildPrepMessage(prep));
      } else if (action.type === "build_profile") {
        navigate("/questionnaire");
      }
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy("");
    }
  }

  return (
    <div>
      <div className="actions-row" style={{ marginTop: 0 }}>
        {actions.map((a, i) => (
          <button
            key={`${a.type}-${i}`}
            type="button"
            className="btn btn-accent btn-small"
            onClick={() => execute(a)}
            disabled={!!busy}
          >
            {busy === a.type ? "…" : a.label}
          </button>
        ))}
      </div>
      {error && <div className="alert alert-error">{error}</div>}
    </div>
  );
}

function buildPrepMessage(prep) {
  const lines = ["C'est fait ! Voici ta préparation d'entretien :",
                 "", `**Ton pitch**`, prep.pitch, ""];
  if (prep.likely_questions.length) {
    lines.push("**Questions probables**");
    prep.likely_questions.forEach((q) => lines.push(`- ${q}`));
    lines.push("");
  }
  if (prep.technical.length) {
    lines.push("**Questions techniques**");
    prep.technical.forEach((q) => lines.push(`- ${q}`));
    lines.push("");
  }
  if (prep.behavioral.length) {
    lines.push("**Questions comportementales**");
    prep.behavioral.forEach((q) => lines.push(`- ${q}`));
    lines.push("");
  }
  if (prep.prep_tips.length) {
    lines.push("**Mes conseils**");
    prep.prep_tips.forEach((t) => lines.push(`- ${t}`));
  }
  return lines.join("\n");
}

export default function Assistant() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [engine, setEngine] = useState(null); // {mode, model, llm_enabled}
  const [messages, setMessages] = useState(() => [
    { role: "assistant", content: OPENINGS[Math.floor(Math.random() * OPENINGS.length)] },
  ]);
  const [links, setLinks] = useState([]);
  const [actions, setActions] = useState([]);
  const [suggestions, setSuggestions] = useState([
    "Quels métiers puis-je viser ?",
    "Quelles compétences me manquent ?",
    "Trouve-moi les offres récentes.",
    "Comment préparer ma candidature ?",
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    api("/assistant/status").then(setEngine).catch(() => {});
  }, []);

  function assistantMessage(content) {
    setMessages((prev) => [...prev, { role: "assistant", content }]);
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  }

  async function send(text) {
    const message = (text ?? input).trim();
    if (!message || busy) return;
    setInput("");
    setBusy(true);
    setLinks([]);
    setActions([]);
    const history = [...messages, { role: "user", content: message }];
    setMessages(history);
    try {
      const res = await api("/assistant", {
        method: "POST",
        body: {
          message,
          history: history
            .slice(-12)
            .map((m) => ({ role: m.role, content: m.content })),
        },
      });
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
      setSuggestions(res.suggestions || []);
      setLinks(res.links || []);
      setActions(res.actions || []);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Désolé, une erreur est survenue : ${err.detail}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page page-narrow">
      <h1>Assistant</h1>
      <p className="page-lead">
        Discute naturellement avec Ori. Il s'appuie sur tes données, peut
        fouiller le web, et agit avec toi : CV, lettre, entretien, profil.
      </p>

      {engine && (
        engine.llm_enabled ? (
          <div className="alert alert-info" style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <span className="badge badge-strong">Modèle connecté</span>
            <span className="small">Ori fonctionne avec ton modèle : <strong>{engine.model || "OpenAI-compatible"}</strong></span>
          </div>
        ) : (
          <div className="alert alert-error" style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
            <span className="badge badge-weak">Mode local</span>
            <span className="small">
              Aucun modèle IA configuré : Ori utilise le moteur de règles local
              (rapide mais limité).
              {" "}
              {user?.role === "admin" ? (
                <Link to="/admin/parametres">Configurer le modèle → Paramètres · LLM</Link>
              ) : (
                "Demande à un administrateur de renseigner la clé API (Paramètres · LLM)."
              )}
            </span>
          </div>
        )
      )}

      <div className="panel">
        <div className="chat-box">
          {messages.map((m, i) => (
            m.role === "user" ? (
              <div key={i} className="chat-msg chat-user">{m.content}</div>
            ) : (
              <div
                key={i}
                className="chat-msg chat-bot chat-msg-md"
                dangerouslySetInnerHTML={{ __html: mdToHtml(m.content) }}
              />
            )
          ))}
          {busy && <div className="chat-msg chat-bot muted">…</div>}
          <div ref={bottomRef} />
        </div>

        {actions.length > 0 && (
          <ActionButtons actions={actions} onExecuted={assistantMessage} />
        )}

        {links.length > 0 && (
          <div className="actions-row" style={{ marginTop: actions.length ? "0.3rem" : 0 }}>
            {links.map((l) => {
              const external = /^https?:\/\//.test(l.href);
              return external ? (
                <a
                  key={`${l.label}-${l.href}`}
                  href={l.href}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-outline btn-small"
                >
                  {l.label}
                </a>
              ) : (
                <button
                  key={`${l.label}-${l.href}`}
                  type="button"
                  className="btn btn-outline btn-small"
                  onClick={() => navigate(mapInternalPath(l.href))}
                >
                  {l.label}
                </button>
              );
            })}
          </div>
        )}

        {suggestions.length > 0 && (
          <div className="chat-suggestions">
            {suggestions.map((s) => (
              <button key={s} type="button" className="suggestion" onClick={() => send(s)}>
                {s}
              </button>
            ))}
          </div>
        )}

        <form
          className="chat-form"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Pose ta question…"
          />
          <button className="btn btn-primary" disabled={busy || !input.trim()}>
            Envoyer
          </button>
        </form>
      </div>
    </div>
  );
}
