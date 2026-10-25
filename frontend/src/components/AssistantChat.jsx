import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { api } from "../api/client.js";
import { mapInternalPath, mdToHtml } from "../lib.js";
import { Icon, I, ArrowIcon } from "./icons.jsx";

// Chat de l'assistant Ori, partagé :
// - page « Assistant » (pleine page, tous les rôles) ;
// - page « Mon agent » (barre de commande compacte, candidat).
// Ori parle naturellement, rend le markdown (gras, listes, liens
// cliquables) et propose des ACTIONS réelles (CV, lettre, entretien,
// profil). L'utilisateur garde toujours le contrôle.

const CANDIDATE_OPENINGS = [
  "Salut ! Moi c'est Ori. Une offre à analyser, un entretien à préparer, une compétence à monter ? Dis-moi tout.",
  "Bonjour ! Prêt à avancer aujourd'hui ? Pose ta question, ou colle le lien d'une offre qui t'intéresse.",
  "Salut ! Besoin d'un coup de main : métiers, formations, CV, entretien ? Je m'occupe du reste.",
  "Bonjour ! Par quoi on commence : explorer des opportunités, monter en compétences, ou préparer une candidature ?",
];

const RECRUITER_OPENINGS = [
  "Salut ! Moi c'est Ori, ton côté recrutement. Décris-moi un poste, je le structure en offre. Ou demande-moi des talents.",
  "Bonjour ! On publie une offre, on cherche des talents, ou on fait le point sur les candidatures reçues ?",
];

const CANDIDATE_SUGGESTIONS = [
  "Trouve-moi des offres en cybersécurité",
  "Pourquoi je ne suis pas retenu ?",
  "Cherche des opportunités à Yaoundé",
  "Prépare ma candidature",
];

const RECRUITER_SUGGESTIONS = [
  "Publie une offre depuis une description",
  "Montre-moi les talents disponibles",
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
        // Chaîne complète : l'offre → galerie de modèles → document.
        navigate(`/opportunites/${action.job_id}?galerie=cv`);
      } else if (action.type === "generate_letter") {
        navigate(`/opportunites/${action.job_id}?galerie=lettre`);
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

export default function AssistantChat({ compact = false, suggestions: starter = null, initialMessage = null, pageContext = null }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isRecruiter = user?.role === "recruiter";
  const openings = isRecruiter ? RECRUITER_OPENINGS : CANDIDATE_OPENINGS;
  const [messages, setMessages] = useState(() => [
    { role: "assistant", content: openings[Math.floor(Math.random() * openings.length)] },
  ]);
  const [links, setLinks] = useState([]);
  const [actions, setActions] = useState([]);
  const [suggestions, setSuggestions] = useState(
    starter || (isRecruiter ? RECRUITER_SUGGESTIONS : CANDIDATE_SUGGESTIONS)
  );
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef(null);
  const sentInitial = useRef(false);

  // Historique persisté (30 jours par défaut) : la conversation reprend
  // là où elle s'était arrêtée. Le mode éphémère n'écrit simplement rien.
  useEffect(() => {
    if (initialMessage) return;
    let alive = true;
    api("/assistant/history")
      .then((data) => {
        if (!alive) return;
        const stored = (data.messages || []).map((m) => ({
          role: m.role,
          content: m.content,
        }));
        if (stored.length > 0) setMessages(stored);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [initialMessage]);

  // Effacement demandé depuis « Mon agent » : le fil revient à zéro.
  useEffect(() => {
    const onCleared = () => {
      setMessages([
        { role: "assistant", content: openings[Math.floor(Math.random() * openings.length)] },
      ]);
    };
    window.addEventListener("orientskill:history-cleared", onCleared);
    return () => {
      window.removeEventListener("orientskill:history-cleared", onCleared);
    };
  }, []);

  useEffect(() => {
    if (!compact) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, compact]);

  // Message initial (lien profond ?q=...) : envoyé une seule fois.
  useEffect(() => {
    if (initialMessage && !sentInitial.current) {
      sentInitial.current = true;
      send(initialMessage);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialMessage]);

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
          context: pageContext || undefined,
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

  // En mode compact, on n'affiche le fil qu'une fois la conversation lancée.
  const visible = compact
    ? messages.filter((_, i) => i > 0 || messages.length > 1)
    : messages;

  const thread = (
    <div className={compact ? "ag-thread" : "chat-box"}>
      {visible.map((m, i) => (
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
  );

  const extras = (
    <>
      {actions.length > 0 && <ActionButtons actions={actions} onExecuted={assistantMessage} />}

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
    </>
  );

  if (compact) {
    return (
      <div className="ag-chat">
        {messages.length > 1 && thread}
        {actions.length > 0 || links.length > 0 ? <div className="ag-chat-extras">{extras}</div> : null}
        <form
          className="ag-composer"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <span className="ag-composer-icon"><Icon d={I.bot} size={20} /></span>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Que voulez-vous que je fasse pour vous ?"
            aria-label="Message à l'assistant"
          />
          <button
            className="ag-send"
            disabled={busy || !input.trim()}
            aria-label="Envoyer"
          >
            <ArrowIcon direction="up" size={16} />
          </button>
        </form>
        {suggestions.length > 0 && (
          <div className="ag-chat-suggestions">
            {suggestions.map((s) => (
              <button key={s} type="button" className="suggestion" onClick={() => send(s)}>
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="panel">
      {thread}
      {extras}
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
  );
}
