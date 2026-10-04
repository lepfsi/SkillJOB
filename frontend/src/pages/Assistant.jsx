import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { mapInternalPath, mdToHtml } from "../lib.js";

// Assistant conversationnel (§26) : dialogue naturel ancré sur les
// données réelles (profil, offres, marché). Suggestions cliquables.
export default function Assistant() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Salut ! Je suis Ori, ton assistant personnel. Je connais ton profil, tes métiers recommandés et tes écarts, et je peux fouiller le web pour toi. Pose ta question, ou colle l'URL d'une offre à analyser.",
    },
  ]);
  const [links, setLinks] = useState([]);
  const [suggestions, setSuggestions] = useState([
    "Quels métiers puis-je viser avec mon profil ?",
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

  async function send(text) {
    const message = (text ?? input).trim();
    if (!message || busy) return;
    setInput("");
    setBusy(true);
    const history = [...messages, { role: "user", content: message }];
    setMessages(history);
    try {
      const res = await api("/assistant", {
        method: "POST",
        body: {
          message,
          history: history
            .filter((m) => m.role !== "system")
            .slice(-10)
            .map((m) => ({ role: m.role, content: m.content })),
        },
      });
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
      setSuggestions(res.suggestions || []);
      setLinks(res.links || []);
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
        Discutez naturellement avec la plateforme : vos réponses sont ancrées
        sur votre profil et les données réelles du marché.
      </p>

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

        {links.length > 0 && (
          <div className="actions-row" style={{ marginTop: 0 }}>
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
            placeholder="Posez votre question…"
          />
          <button className="btn btn-primary" disabled={busy || !input.trim()}>
            Envoyer
          </button>
        </form>
      </div>
    </div>
  );
}
