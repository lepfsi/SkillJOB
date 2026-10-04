import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { fmtDateTime, STATUS_LABELS } from "../lib.js";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";

// Messagerie interne : recruteurs contactent les talents, les talents
// répondent. Tout passe par la plateforme : pas de coordonnées exposées.

function ThreadsList({ threads, onOpen }) {
  return (
    <div>
      {threads.length === 0 && (
        <Empty title="Aucune conversation">
          <p>
            Les recruteurs intéressés par votre profil vous écriront ici.
            Vous y retrouverez aussi vos échanges avec les entreprises.
          </p>
        </Empty>
      )}
      {threads.map((t) => (
        <button
          key={t.other_user_id}
          type="button"
          className={`msg-thread-user${t.unread ? " msg-unread" : ""}`}
          onClick={() => onOpen(t.other_user_id)}
        >
          <div style={{ textAlign: "left", minWidth: 0 }}>
            <strong>{t.other_name}</strong>
            <span className="small muted"> · {t.other_role === "recruiter" ? "Recruteur" : t.other_role}</span>
            {t.other_company && (
              <div className="small muted">
                Entreprise : {t.other_company.name}
                {t.other_company.sector ? ` · ${t.other_company.sector}` : ""}
              </div>
            )}
            <div className="small muted" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {t.last_body}
            </div>
          </div>
          <div style={{ textAlign: "right", flexShrink: 0 }}>
            {t.last_at && <div className="small muted">{fmtDateTime(t.last_at)}</div>}
            {t.unread > 0 && <span className="badge badge-strong">{t.unread} non lu(s)</span>}
          </div>
        </button>
      ))}
    </div>
  );
}

function ThreadView({ otherId, onBack }) {
  const [data, setData] = useState(null);
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const me = JSON.parse(localStorage.getItem("orientskill_user") || "null");

  useEffect(() => {
    api(`/messages/${otherId}`)
      .then(setData)
      .catch((e) => setError(e.detail));
  }, [otherId]);

  async function send(e) {
    e.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    setError("");
    try {
      await api("/messages", { method: "POST", body: { recipient_id: otherId, body } });
      setBody("");
      const updated = await api(`/messages/${otherId}`);
      setData(updated);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  if (!data) {
    return <Loader />;
  }

  const identity = data.identity || {};
  const company = identity.company;

  return (
    <div>
      <button className="btn btn-ghost btn-small" onClick={onBack}>← Conversations</button>

      <div className="profile-card" style={{ marginTop: "0.8rem" }}>
        <div style={{ flex: 1 }}>
          <h2 style={{ marginBottom: 0 }}>{identity.name}</h2>
          <p className="job-meta" style={{ margin: "0.2rem 0" }}>
            {identity.role === "recruiter" ? "Recruteur" : identity.role === "admin" ? "Équipe OrientSkill" : "Candidat"}
          </p>
          {company && (
            <>
              <p className="small" style={{ margin: "0.2rem 0" }}>
                <strong>{company.name}</strong>
                {company.sector ? ` · ${company.sector}` : ""}
                {company.location ? ` · ${company.location}` : ""}
              </p>
              {company.description && (
                <p className="small muted" style={{ margin: 0 }}>{company.description}</p>
              )}
            </>
          )}
        </div>
      </div>

      <div className="panel" style={{ display: "flex", flexDirection: "column", marginTop: "0.8rem" }}>
        {data.messages.map((m) => (
          <div
            key={m.id}
            className={`msg-bubble ${m.sender_id === me?.id ? "msg-mine" : "msg-theirs"}`}
          >
            {m.body}
            <div className="small" style={{ opacity: 0.7, marginTop: "0.25rem" }}>
              {fmtDateTime(m.created_at)}
            </div>
          </div>
        ))}
      </div>
      <ErrorNote error={error} />
      <form className="chat-form" onSubmit={send}>
        <input
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Votre message…"
        />
        <button className="btn btn-primary" disabled={busy || !body.trim()}>
          Envoyer
        </button>
      </form>
    </div>
  );
}

export default function Messages() {
  const [threads, setThreads] = useState(null);
  const [error, setError] = useState("");
  const { otherId } = useParams();
  const navigate = useNavigate();

  const loadThreads = () => {
    api("/messages").then(setThreads).catch((e) => setError(e.detail));
  };

  useEffect(() => {
    loadThreads();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [otherId]);

  if (error && !threads) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!threads) {
    return <div className="page"><Loader /></div>;
  }

  return (
    <div className="page page-narrow">
      <h1>Messages</h1>
      <p className="page-lead">
        Vos échanges avec les recruteurs et les talents, directement sur la
        plateforme.
      </p>
      {otherId ? (
        <ThreadView otherId={Number(otherId)} onBack={() => navigate("/messages")} />
      ) : (
        <ThreadsList threads={threads} onOpen={(id) => navigate(`/messages/${id}`)} />
      )}
    </div>
  );
}
