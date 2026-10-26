import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { api } from "../api/client.js";
import { mapInternalPath, mdToHtml, relTime } from "../lib.js";
import { Icon, I, ArrowIcon } from "./icons.jsx";
import AgentHistoryControls from "./AgentHistoryControls.jsx";

// Chat de l'assistant Ori :
// - page « Assistant » (pleine page) ;
// - page « Mon agent » (version compacte).
// L'utilisateur peut empiler plusieurs conversations, en ouvrir une,
// la fermer, la reprendre ou la supprimer. Les réglages d'historique
// restent attachés à la conversation affichée.

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
  const lines = ["C'est fait ! Voici ta préparation d'entretien :", "", `**Ton pitch**`, prep.pitch, ""];
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

export default function AssistantChat({
  compact = false,
  suggestions: starter = null,
  initialMessage = null,
  pageContext = null,
}) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isRecruiter = user?.role === "recruiter";
  const openings = isRecruiter ? RECRUITER_OPENINGS : CANDIDATE_OPENINGS;
  const defaultSuggestions = starter || (isRecruiter ? RECRUITER_SUGGESTIONS : CANDIDATE_SUGGESTIONS);

  const [conversations, setConversations] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [links, setLinks] = useState([]);
  const [actions, setActions] = useState([]);
  const [suggestions, setSuggestions] = useState(defaultSuggestions);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [closed, setClosed] = useState(true);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);
  const sentInitial = useRef(false);

  const openingMessage = () => ({
    role: "assistant",
    content: openings[Math.floor(Math.random() * openings.length)],
  });

  async function loadConversations() {
    try {
      const rows = await api("/assistant/conversations");
      setConversations(rows || []);
      // Par défaut, les conversations restent fermées : l'utilisateur
      // choisit explicitement celle qu'il veut reprendre.
      if (initialMessage) {
        if ((rows || []).length > 0) {
          await openConversation(rows[0].id, rows);
        } else {
          await createConversation();
        }
      } else {
        setActiveConversation((rows || [])[0] || null);
        setMessages([]);
        setClosed(true);
      }
    } catch (err) {
      setConversations([]);
      setError(err.detail || "Impossible de charger vos conversations.");
    }
  }

  async function openConversation(conversationId, knownRows = null) {
    try {
      const data = await api(`/assistant/conversations/${conversationId}`);
      setActiveConversation(data.conversation);
      const stored = (data.messages || []).map((m) => ({
        role: m.role,
        content: m.content,
      }));
      setMessages(stored.length > 0 ? stored : [openingMessage()]);
      setLinks([]);
      setActions([]);
      setSuggestions(defaultSuggestions);
      setClosed(false);
      setError("");
      if (knownRows) setConversations(knownRows);
    } catch (err) {
      setClosed(true);
      setError(err.detail || "Impossible d'ouvrir cette conversation.");
    }
  }

  async function createConversation() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const created = await api("/assistant/conversations", {
        method: "POST",
        body: { title: "Nouvelle conversation" },
      });
      setConversations((prev) => [created, ...prev.filter((c) => c.id !== created.id)]);
      setActiveConversation(created);
      setMessages([openingMessage()]);
      setLinks([]);
      setActions([]);
      setSuggestions(defaultSuggestions);
      setClosed(false);
    } catch (err) {
      setError(err.detail || "Impossible de créer une nouvelle conversation.");
    } finally {
      setBusy(false);
    }
  }

  async function afterConversationDeleted(conversationId) {
    const remaining = conversations.filter((c) => c.id !== conversationId);
    setConversations(remaining);
    if (activeConversation?.id !== conversationId) return;
    if (remaining.length > 0) {
      await openConversation(remaining[0].id, remaining);
      return;
    }
    const created = await api("/assistant/conversations", {
      method: "POST",
      body: { title: "Nouvelle conversation" },
    });
    setConversations([created]);
    setActiveConversation(created);
    setMessages([openingMessage()]);
    setLinks([]);
    setActions([]);
    setSuggestions(defaultSuggestions);
    setClosed(false);
  }

  async function deleteConversation(conversationId) {
    const row = conversations.find((c) => c.id === conversationId);
    if (!row) return;
    if (!window.confirm(`Effacer la conversation « ${row.title} » ?`)) return;
    setBusy(true);
    try {
      await api(`/assistant/conversations/${conversationId}`, { method: "DELETE" });
      await afterConversationDeleted(conversationId);
    } catch (err) {
      setError(err.detail || "Impossible de supprimer cette conversation.");
    } finally {
      setBusy(false);
    }
  }

  function assistantMessage(content) {
    setMessages((prev) => [...prev, { role: "assistant", content }]);
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  }

  async function send(text) {
    const message = (text ?? input).trim();
    if (!message || busy || !activeConversation) return;
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
          conversation_id: activeConversation.id,
          context: pageContext || undefined,
          history: history
            .slice(-12)
            .map((m) => ({ role: m.role, content: m.content })),
        },
      });
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
      setSuggestions(res.suggestions || defaultSuggestions);
      setLinks(res.links || []);
      setActions(res.actions || []);
      const rows = await api("/assistant/conversations");
      setConversations(rows || []);
      const refreshed = (rows || []).find((c) => c.id === activeConversation.id);
      if (refreshed) setActiveConversation(refreshed);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Désolé, une erreur est survenue : ${err.detail}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!compact) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, compact]);

  useEffect(() => {
    if (initialMessage && !sentInitial.current && activeConversation) {
      sentInitial.current = true;
      setClosed(false);
      send(initialMessage);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialMessage, activeConversation]);

  const thread = (
    <div className={compact ? "ag-thread" : "chat-box"}>
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
  );

  const conversationList = (
    <div className="chat-conversations">
      <div className="chat-conversations-head">
        <h3>Mes conversations</h3>
        <button
          type="button"
          className="btn btn-primary btn-small"
          onClick={createConversation}
          disabled={busy}
        >
          Nouvelle conversation
        </button>
      </div>
      <div className="chat-conversation-stack">
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`chat-conversation-row${c.id === activeConversation?.id && !closed ? " is-active" : ""}`}
          >
            <button
              type="button"
              className="chat-conversation-main"
              onClick={() => openConversation(c.id)}
            >
              <span className="chat-conversation-title">{c.title}</span>
              <span className="chat-conversation-last">
                {c.last_message ? c.last_message.slice(0, 90) : "Nouvelle conversation"}
              </span>
              <span className="chat-conversation-meta">
                {c.message_count} message{c.message_count === 1 ? "" : "s"} · {relTime(c.updated_at)}
              </span>
            </button>
            <div className="chat-conversation-actions">
              <button
                type="button"
                className="btn btn-outline btn-small"
                onClick={() => openConversation(c.id)}
              >
                Ouvrir
              </button>
              <button
                type="button"
                className="btn btn-remove btn-small"
                onClick={() => deleteConversation(c.id)}
              >
                Supprimer
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const actionExtras = (
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
    </>
  );

  const suggestionRow = suggestions.length > 0 && (
    <div className="chat-suggestions">
      {suggestions.map((s) => (
        <button key={s} type="button" className="suggestion" onClick={() => send(s)}>
          {s}
        </button>
      ))}
    </div>
  );

  const header = (
    <header className="chat-header">
      <div className="chat-header-main">
        <span className="chat-header-icon"><Icon d={I.bot} size={18} /></span>
        <div>
          <h2>{closed ? "Mes conversations" : activeConversation?.title}</h2>
          <p>
            {closed
              ? "Reprenez une conversation existante ou ouvrez-en une nouvelle."
              : `${activeConversation?.message_count || messages.length} message${(activeConversation?.message_count || messages.length) === 1 ? "" : "s"} · ${activeConversation?.history_mode === "ephemeral" ? "éphémère" : "conservée"}`}
          </p>
        </div>
      </div>
      <div className="chat-header-actions">
        <button
          type="button"
          className="btn btn-outline btn-small"
          onClick={createConversation}
          disabled={busy}
        >
          Nouvelle
        </button>
        {!closed && (
          <button
            type="button"
            className="btn btn-ghost btn-small"
            onClick={() => setClosed(true)}
          >
            Fermer
          </button>
        )}
      </div>
    </header>
  );

  const errorBanner = error ? (
    <div className="alert alert-error" role="alert">{error}</div>
  ) : null;

  if (compact) {
    return (
      <div className="ag-chat">
        {header}
        {errorBanner}
        {closed ? conversationList : (
          <>
            <AgentHistoryControls
              conversationId={activeConversation?.id}
              onUpdated={(row) => setActiveConversation(row)}
              onDeleted={afterConversationDeleted}
            />
            {thread}
            {actions.length > 0 || links.length > 0 ? (
              <div className="ag-chat-extras">{actionExtras}</div>
            ) : null}
          </>
        )}
        {!closed && (
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
            <button className="ag-send" disabled={busy || !input.trim()} aria-label="Envoyer">
              <ArrowIcon direction="up" size={16} />
            </button>
          </form>
        )}
        {!closed && suggestions.length > 0 && (
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
    <div className="panel chat-panel">
      {header}
      {errorBanner}
      {closed ? conversationList : (
        <>
          <AgentHistoryControls
            conversationId={activeConversation?.id}
            onUpdated={(row) => setActiveConversation(row)}
            onDeleted={(id) => deleteConversation(id)}
          />
          {thread}
          {actionExtras}
          {suggestionRow}
        </>
      )}
      {!closed && (
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
      )}
    </div>
  );
}
