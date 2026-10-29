import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { Icon, I, ArrowIcon } from "../components/icons.jsx";
import CompanyLogo from "../components/CompanyLogo.jsx";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";

// Messagerie interne modernisée : liste des conversations et fil de discussion
// en deux volets sur écran large, un seul volet sur écran étroit. Tout passe
// par la plateforme : aucune coordonnée personnelle n'est exposée (§25), mais
// le talent voit toujours qui lui écrit (nom, rôle, entreprise).

const ROLE_LABELS = {
  recruiter: "Recruteur",
  candidate: "Candidat",
  admin: "Équipe OrientSkill",
};
const ROLE_TONES = { recruiter: "green", candidate: "blue", admin: "violet" };

function roleLabel(role) {
  return ROLE_LABELS[role] || "Interlocuteur";
}

function dayLabel(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const startOf = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const days = Math.round((startOf(now) - startOf(d)) / 86400000);
  if (days === 0) return "Aujourd'hui";
  if (days === 1) return "Hier";
  if (days < 7) return d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
}

function timeOf(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

// Horodatage compact de la liste : heure du jour, « Hier », puis la date.
function listStamp(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const startOf = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const days = Math.round((startOf(now) - startOf(d)) / 86400000);
  if (days === 0) return timeOf(iso);
  if (days === 1) return "Hier";
  if (days < 7) return d.toLocaleDateString("fr-FR", { weekday: "short" });
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

function Avatar({ name, role, logoUrl, size = 42 }) {
  const tone = ROLE_TONES[role] || "slate";
  return (
    <CompanyLogo
      name={name}
      logoUrl={logoUrl}
      className={`msg-avatar msg-tone-${tone}`}
      style={{ width: size, height: size, fontSize: `${Math.round(size * 0.36)}px` }}
    />
  );
}

function ThreadsList({ threads, activeId, onOpen, query, setQuery }) {
  if (threads.length === 0) {
    return (
      <p className="msg-side-empty small muted">
        {query ? "Aucune conversation ne correspond à cette recherche." : "Aucune conversation."}
      </p>
    );
  }
  return (
    <div className="msg-threads">
      {threads.map((t) => (
        <button
          key={t.other_user_id}
          type="button"
          className={`msg-thread${t.other_user_id === activeId ? " is-active" : ""}${t.unread > 0 ? " is-unread" : ""}`}
          onClick={() => onOpen(t.other_user_id)}
        >
          <Avatar
            name={t.other_name}
            role={t.other_role}
            logoUrl={t.other_company?.logo_url}
          />
          <span className="msg-thread-main">
            <span className="msg-thread-top">
              <strong>{t.other_name}</strong>
              <span className="msg-thread-time">{listStamp(t.last_at)}</span>
            </span>
            <span className="msg-thread-sub">
              {roleLabel(t.other_role)}
              {t.other_company?.name ? ` · ${t.other_company.name}` : ""}
            </span>
            <span className="msg-thread-preview">{t.last_body}</span>
          </span>
          {t.unread > 0 && <span className="msg-thread-count">{t.unread}</span>}
        </button>
      ))}
    </div>
  );
}

function ThreadView({ otherId, onBack, onSent }) {
  const [data, setData] = useState(null);
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { user } = useAuth();
  const feedRef = useRef(null);

  function load() {
    return api(`/messages/${otherId}`)
      .then((d) => {
        setData(d);
        return d;
      })
      .catch((e) => setError(e.detail));
  }

  useEffect(() => {
    setData(null);
    setError("");
    load().then(() => onSent());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [otherId]);

  const feed = useMemo(() => {
    const items = [];
    let lastDay = null;
    let lastSender = null;
    (data?.messages || []).forEach((m) => {
      const day = new Date(m.created_at).toDateString();
      if (day !== lastDay) {
        items.push({ kind: "day", key: `day-${day}-${m.id}`, label: dayLabel(m.created_at) });
        lastDay = day;
        lastSender = null;
      }
      items.push({
        kind: "msg",
        m,
        mine: m.sender_id === user?.id,
        first: m.sender_id !== lastSender,
      });
      lastSender = m.sender_id;
    });
    return items;
  }, [data, user]);

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [feed]);

  async function send(e) {
    e.preventDefault();
    const text = body.trim();
    if (!text) return;
    setBusy(true);
    setError("");
    try {
      await api("/messages", { method: "POST", body: { recipient_id: otherId, body: text } });
      setBody("");
      await load();
      onSent();
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(e);
    }
  }

  if (!data) {
    return (
      <section className="msg-pane">
        <div className="msg-pane-loading"><Loader /></div>
      </section>
    );
  }

  const identity = data.identity || {};
  const company = identity.company;

  return (
    <section className="msg-pane">
      <header className="msg-pane-head">
        <button type="button" className="msg-back" onClick={onBack} aria-label="Retour aux conversations">
          <ArrowIcon direction="right" size={14} />
        </button>
        <Avatar
          name={identity.name}
          role={identity.role}
          logoUrl={company?.logo_url}
          size={44}
        />
        <div className="msg-pane-id">
          <strong>{identity.name}</strong>
          <span className="small muted">
            {roleLabel(identity.role)}
            {company?.name ? ` · ${company.name}` : ""}
            {company?.location ? ` · ${company.location}` : ""}
          </span>
        </div>
      </header>

      {company?.description && <p className="msg-company small muted">{company.description}</p>}

      <div className="msg-feed" ref={feedRef}>
        {feed.map((item) =>
          item.kind === "day" ? (
            <div className="msg-day" key={item.key}>
              <span>{item.label}</span>
            </div>
          ) : (
            <div key={item.m.id} className={`msg-row ${item.mine ? "is-mine" : "is-theirs"}`}>
              {!item.mine && (item.first
                ? <Avatar name={identity.name} role={identity.role} logoUrl={company?.logo_url} size={30} />
                : <span className="msg-avatar-gap" />)}
              <div className={`msg-bubble ${item.mine ? "msg-mine" : "msg-theirs"}`}>
                <p className="msg-text">{item.m.body}</p>
                <span className="msg-meta">
                  {timeOf(item.m.created_at)}
                  {item.m.job_id ? (
                    <Link className="msg-job-link" to={`/opportunites/${item.m.job_id}`}>
                      Offre liée
                    </Link>
                  ) : null}
                </span>
              </div>
            </div>
          )
        )}
      </div>

      <ErrorNote error={error} />

      <form className="msg-composer" onSubmit={send}>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          placeholder="Écrivez votre message…"
          aria-label="Votre message"
        />
        <button className="btn btn-primary" disabled={busy || !body.trim()}>
          {busy ? "Envoi…" : "Envoyer"}
        </button>
      </form>
      <p className="msg-hint small muted">
        Entrée pour envoyer · Maj + Entrée pour un retour à la ligne
      </p>
    </section>
  );
}

export default function Messages() {
  const [threads, setThreads] = useState(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
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

  const activeId = otherId ? Number(otherId) : null;
  const unreadTotal = threads.reduce((n, t) => n + (t.unread || 0), 0);
  const q = query.trim().toLowerCase();
  const visible = q
    ? threads.filter((t) =>
        [t.other_name, t.other_company?.name, t.last_body, roleLabel(t.other_role)]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(q)
      )
    : threads;

  return (
    <div className={`page msg-page${activeId ? " has-thread" : ""}`}>
      <header className="msg-page-head">
        <div>
          <h1>Messages</h1>
          <p className="page-lead">
            Vos échanges avec les recruteurs et les talents, directement sur la plateforme.
          </p>
        </div>
        <div className="msg-stats">
          <span className="msg-stat">
            <Icon d={I.chat} size={15} />
            {threads.length} conversation{threads.length > 1 ? "s" : ""}
          </span>
          {unreadTotal > 0 && (
            <span className="msg-stat msg-stat-alert">
              <span className="msg-dot" />
              {unreadTotal} non lu{unreadTotal > 1 ? "s" : ""}
            </span>
          )}
        </div>
      </header>

      {threads.length === 0 ? (
        <Empty title="Aucune conversation">
          <p>
            Les recruteurs intéressés par votre profil vous écriront ici.
            Vous y retrouverez aussi vos échanges avec les entreprises.
          </p>
        </Empty>
      ) : (
        <div className="msg-shell">
          <aside className="msg-side">
            <div className="msg-search">
              <Icon d={I.search} size={15} />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Rechercher une conversation…"
                aria-label="Rechercher une conversation"
              />
            </div>
            <ThreadsList
              threads={visible}
              activeId={activeId}
              onOpen={(id) => navigate(`/messages/${id}`)}
              query={q}
              setQuery={setQuery}
            />
          </aside>

          {activeId ? (
            <ThreadView
              otherId={activeId}
              onBack={() => navigate("/messages")}
              onSent={loadThreads}
            />
          ) : (
            <section className="msg-pane msg-pane-empty">
              <span className="msg-pane-empty-icon"><Icon d={I.chat} size={26} /></span>
              <h2>Choisissez une conversation</h2>
              <p className="muted">
                Sélectionnez un interlocuteur à gauche pour lire et poursuivre l'échange.
              </p>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
