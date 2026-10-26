import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { relTime, fmtDateTime } from "../lib.js";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";
import { Icon, I } from "../components/icons.jsx";

// Notifications : événements calculés pour le candidat (offres, échéances,
// entretiens, réponses de l'administration). La messagerie interne reste
// séparée : les messages des recruteurs ne sont pas dupliqués ici.

const KIND_META = {
  new_job: {
    label: "Nouvelle offre",
    icon: "briefcase",
    tone: "job",
    category: "offers",
  },
  strong_match: {
    label: "Correspondance forte",
    icon: "target",
    tone: "match",
    category: "offers",
  },
  expiring: {
    label: "Échéance proche",
    icon: "clock",
    tone: "urgent",
    category: "offers",
  },
  application: {
    label: "Candidature",
    icon: "clipboard",
    tone: "application",
    category: "applications",
  },
  interview: {
    label: "Entretien",
    icon: "users",
    tone: "interview",
    category: "interviews",
  },
  learning: {
    label: "Formation",
    icon: "cap",
    tone: "learning",
    category: "learning",
  },
  trend: {
    label: "Marché",
    icon: "trending",
    tone: "market",
    category: "learning",
  },
  report: {
    label: "Signalement",
    icon: "shield",
    tone: "admin",
    category: "admin",
  },
  appeal: {
    label: "Recours",
    icon: "shield",
    tone: "admin",
    category: "admin",
  },
  verification: {
    label: "Vérification",
    icon: "shield",
    tone: "admin",
    category: "admin",
  },
};

const CATEGORIES = [
  { key: "all", label: "Tout", icon: "bell" },
  { key: "offers", label: "Offres", icon: "briefcase" },
  { key: "applications", label: "Candidatures", icon: "clipboard" },
  { key: "interviews", label: "Entretiens", icon: "users" },
  { key: "learning", label: "Formation et marché", icon: "cap" },
  { key: "admin", label: "Administration", icon: "shield" },
];

function metaFor(kind) {
  return KIND_META[kind] || {
    label: kind || "Notification",
    icon: "bell",
    tone: "neutral",
    category: "other",
  };
}

function Actions({ event }) {
  const actions = [];
  if (event.job_id && event.kind !== "interview") {
    actions.push(
      <Link
        className="notif-action"
        to={`/opportunites/${event.job_id}`}
        key="job"
      >
        Voir l'offre <Icon d={I.arrow} size={14} />
      </Link>
    );
  }
  if (event.kind === "interview") {
    actions.push(
      <Link className="notif-action" to="/entretiens" key="interview">
        Répondre à l'invitation <Icon d={I.arrow} size={14} />
      </Link>
    );
  }
  if (event.kind === "application") {
    actions.push(
      <Link className="notif-action" to="/candidatures" key="application">
        Suivre mes candidatures <Icon d={I.arrow} size={14} />
      </Link>
    );
  }
  if (event.kind === "learning") {
    actions.push(
      <Link className="notif-action" to="/learning" key="learning">
        Explorer les formations <Icon d={I.arrow} size={14} />
      </Link>
    );
  }
  if (event.kind === "trend") {
    actions.push(
      <Link className="notif-action" to="/" key="trend">
        Voir mon tableau de bord <Icon d={I.arrow} size={14} />
      </Link>
    );
  }
  if (event.kind === "verification") {
    actions.push(
      <Link className="notif-action" to="/profil" key="verification">
        Voir mon profil <Icon d={I.arrow} size={14} />
      </Link>
    );
  }
  if (!actions.length) return null;
  return <div className="notif-card-actions">{actions}</div>;
}

export default function Notifications() {
  const [events, setEvents] = useState(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [seen, setSeen] = useState(false);
  const [initialUnread, setInitialUnread] = useState(0);

  useEffect(() => {
    let active = true;
    api("/notifications")
      .then((data) => {
        if (!active) return;
        setEvents(data);
        setInitialUnread(data.filter((event) => event.unread).length);
        // La consultation de la rubrique marque les événements comme lus.
        // Le badge de la barre supérieure se met à jour immédiatement.
        api("/notifications/seen", { method: "POST" })
          .then(() => {
            if (!active) return;
            setSeen(true);
            window.dispatchEvent(new Event("orientskill:notifications-seen"));
          })
          .catch(() => {});
      })
      .catch((err) => {
        if (active) setError(err.detail);
      });
    return () => {
      active = false;
    };
  }, []);

  const counts = useMemo(() => {
    const next = { all: events?.length || 0 };
    for (const category of CATEGORIES) {
      if (category.key !== "all") next[category.key] = 0;
    }
    for (const event of events || []) {
      const category = metaFor(event.kind).category;
      if (category in next) next[category] += 1;
    }
    return next;
  }, [events]);

  const activeCategories = useMemo(
    () =>
      CATEGORIES.filter(
        (category) =>
          category.key !== "all" && (counts[category.key] || 0) > 0
      ).length,
    [counts]
  );

  const filtered = useMemo(() => {
    if (!events) return [];
    if (filter === "all") return events;
    return events.filter(
      (event) => metaFor(event.kind).category === filter
    );
  }, [events, filter]);

  const groups = useMemo(() => {
    const result = [];
    let current = null;
    for (const event of filtered) {
      const label = relTime(event.at);
      if (!current || current.label !== label) {
        current = { label, items: [] };
        result.push(current);
      }
      current.items.push(event);
    }
    return result;
  }, [filtered]);

  if (error) {
    return (
      <div className="page">
        <ErrorNote error={error} />
      </div>
    );
  }
  if (!events) {
    return (
      <div className="page">
        <Loader />
      </div>
    );
  }

  const unreadLabel = initialUnread > 1 ? "nouvelles" : "nouvelle";

  return (
    <div className="page notif-page">
      <header className="notif-hero">
        <div className="notif-hero-copy">
          <span className="notif-kicker">
            <Icon d={I.bell} size={14} /> Centre de notifications
          </span>
          <h1>Notifications</h1>
          <p>
            Votre veille professionnelle, distincte de vos messages. Offres,
            échéances, candidatures et entretiens sont rassemblés ici pour
            vous aider à passer à l'action.
          </p>
          <div className="notif-hero-meta">
            <span
              className={`notif-status${seen ? " is-ok" : ""}`}
              aria-live="polite"
            >
              <Icon d={I.check} size={14} />
              {seen ? "Tout est à jour" : "Mise à jour en cours"}
            </span>
            <span>
              {initialUnread > 0
                ? `${initialUnread} ${unreadLabel} depuis votre dernière visite`
                : "Aucune nouvelle depuis votre dernière visite"}
            </span>
          </div>
        </div>
        <div className="notif-hero-stats">
          <div className="notif-hero-stat">
            <strong>{events.length}</strong>
            <span>Notifications</span>
          </div>
          <div className="notif-hero-stat">
            <strong>{initialUnread}</strong>
            <span>Nouvelles</span>
          </div>
          <div className="notif-hero-stat">
            <strong>{activeCategories}</strong>
            <span>Catégories</span>
          </div>
        </div>
      </header>

      <div className="notif-layout">
        <main className="notif-main">
          <div className="notif-toolbar">
            <div
              className="notif-filters"
              role="group"
              aria-label="Filtrer les notifications"
            >
              {CATEGORIES.map((category) => (
                <button
                  key={category.key}
                  type="button"
                  className={`notif-filter${
                    filter === category.key ? " is-active" : ""
                  }`}
                  onClick={() => setFilter(category.key)}
                  aria-pressed={filter === category.key}
                >
                  <Icon d={I[category.icon]} size={14} />
                  {category.label}
                  <span className="notif-filter-count">
                    {counts[category.key] || 0}
                  </span>
                </button>
              ))}
            </div>
            <Link className="notif-messages-link" to="/messages">
              <Icon d={I.chat} size={15} />
              Messages
              <Icon d={I.arrow} size={14} />
            </Link>
          </div>

          {events.length === 0 ? (
            <Empty title="Aucune notification pour le moment">
              <p>
                Dès qu'une offre correspondant à votre profil apparaîtra,
                qu'une échéance approchera ou qu'un entretien sera proposé,
                vous le retrouverez ici. Complétez votre profil pour recevoir
                des recommandations pertinentes.
              </p>
              <Link className="btn btn-outline" to="/opportunites">
                Parcourir les opportunités
              </Link>
            </Empty>
          ) : filtered.length === 0 ? (
            <div className="notif-filter-empty">
              <span className="notif-filter-empty-icon">
                <Icon d={I.filter} size={20} />
              </span>
              <h2>Aucune notification dans cette catégorie</h2>
              <p>
                Essayez un autre filtre ou consultez l'ensemble de votre
                veille.
              </p>
              <button
                type="button"
                className="btn btn-outline btn-small"
                onClick={() => setFilter("all")}
              >
                Afficher tout
              </button>
            </div>
          ) : (
            groups.map((group) => (
              <section className="notif-day" key={group.label}>
                <div className="notif-day-head">
                  <h2>{group.label}</h2>
                  <span className="notif-day-count">
                    {group.items.length}
                  </span>
                </div>
                <div className="notif-list">
                  {group.items.map((event) => {
                    const meta = metaFor(event.kind);
                    // Le marquage côté serveur est immédiat, mais la carte
                    // reste signalée comme nouvelle pendant cette visite.
                    const isUnread = Boolean(event.unread);
                    return (
                      <article
                        key={event.id}
                        className={`notif-card${
                          isUnread ? " is-unread" : ""
                        }`}
                      >
                        <span
                          className={`notif-icon notif-tone-${meta.tone}`}
                        >
                          <Icon d={I[meta.icon]} size={18} />
                        </span>
                        <div className="notif-card-body">
                          <div className="notif-card-top">
                            <span className="notif-kind">{meta.label}</span>
                            <span className="notif-date">
                              <Icon d={I.clock} size={12} />
                              {fmtDateTime(event.at)}
                            </span>
                          </div>
                          <p>{event.message}</p>
                          <Actions event={event} />
                        </div>
                      </article>
                    );
                  })}
                </div>
              </section>
            ))
          )}
        </main>

        <aside className="notif-side">
          <section className="notif-side-card">
            <div className="notif-side-head">
              <span className="notif-side-icon">
                <Icon d={I.chart} size={18} />
              </span>
              <div>
                <h2>En un coup d'œil</h2>
                <p>Votre veille par catégorie.</p>
              </div>
            </div>
            <div className="notif-side-list">
              {CATEGORIES.filter((category) => category.key !== "all").map(
                (category) => (
                  <button
                    key={category.key}
                    type="button"
                    className={`notif-side-row${
                      filter === category.key ? " is-active" : ""
                    }`}
                    onClick={() => setFilter(category.key)}
                  >
                    <span>
                      <Icon d={I[category.icon]} size={15} />
                      {category.label}
                    </span>
                    <span className="notif-side-count">
                      {counts[category.key] || 0}
                    </span>
                  </button>
                )
              )}
            </div>
          </section>

          <section className="notif-side-card notif-side-note">
            <span className="notif-side-icon">
              <Icon d={I.chat} size={18} />
            </span>
            <h2>Messages séparés</h2>
            <p>
              Les échanges avec les recruteurs restent dans la messagerie.
              Les notifications ne les dupliquent pas.
            </p>
            <Link className="btn btn-outline btn-small" to="/messages">
              Ouvrir Messages
            </Link>
          </section>

          <section className="notif-side-card">
            <h2>Dernière activité</h2>
            <p className="small muted">
              {events[0]
                ? fmtDateTime(events[0].at)
                : "Aucune activité enregistrée"}
            </p>
            <p className="small muted">
              Les notifications sont recalculées à partir de votre profil et
              de vos démarches. Elles sont marquées comme lues dès leur
              consultation.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
