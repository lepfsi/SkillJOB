import { NavLink, useNavigate, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { api } from "../api/client.js";
import { Icon, I } from "./icons.jsx";

// Sidebar « produit pro » : icônes SVG sobres, aucun liseré, highlight
// discret au survol et à l'activation, sections pliables à chevron
// fluide, badge de messages bien visible en tête.

const CANDIDATE_NAV_GROUPS = [
  {
    section: null,
    items: [
      { to: "/", label: "Dashboard", icon: "home", end: true },
      { to: "/messages", label: "Messages", icon: "chat", messages: true },
      { to: "/assistant", label: "Assistant", icon: "spark" },
    ],
  },
  {
    section: "Opportunités",
    items: [
      { to: "/opportunites", label: "Offres d'emploi", icon: "briefcase" },
      { to: "/programmes", label: "Programmes publics", icon: "landmark" },
      { to: "/entrepreneuriat", label: "Entrepreneuriat", icon: "rocket" },
      { to: "/candidatures", label: "Mes candidatures", icon: "clipboard" },
    ],
  },
  {
    section: "Mon parcours",
    items: [
      { to: "/carriere", label: "Carrière", icon: "compass" },
      { to: "/competences", label: "Compétences", icon: "zap" },
      { to: "/learning", label: "Learning", icon: "book" },
      { to: "/documents", label: "Documents", icon: "file" },
      { to: "/profil", label: "Profil", icon: "user" },
    ],
  },
  {
    section: "Compte",
    items: [
      { to: "/parametres-compte", label: "Paramètres", icon: "settings" },
    ],
  },
];

const RECRUITER_NAV = [
  { to: "/recruteur", label: "Accueil recruteur", icon: "home", end: true },
  { to: "/recruteur/offres", label: "Mes offres", icon: "briefcase" },
  { to: "/recruteur/candidats", label: "Talents", icon: "users" },
  { to: "/recruteur/shortlists", label: "Shortlists", icon: "clipboard" },
  { to: "/messages", label: "Messages", icon: "chat", messages: true },
  { to: "/parametres-compte", label: "Paramètres", icon: "settings" },
];

const ADMIN_NAV_GROUPS = [
  {
    section: "Pilotage",
    items: [
      { to: "/admin", label: "Vue générale", icon: "chart", end: true },
      { to: "/admin/institutionnel", label: "Analyse institutionnelle", icon: "chart" },
      { to: "/admin/skill-graph", label: "Skill Graph", icon: "graph" },
    ],
  },
  {
    section: "Contenus",
    items: [
      { to: "/admin/offres", label: "Base d'offres", icon: "database" },
      { to: "/admin/sources", label: "Sources & collecte", icon: "globe" },
      { to: "/admin/contenus", label: "Contenus publics", icon: "layers" },
      { to: "/admin/verifications", label: "Vérifications", icon: "shield" },
    ],
  },
  {
    section: "Système",
    items: [
      { to: "/admin/utilisateurs", label: "Utilisateurs", icon: "users" },
      { to: "/admin/parametres", label: "Paramètres plateforme", icon: "settings" },
      { to: "/admin/connecteurs", label: "Connecteurs", icon: "link" },
      { to: "/messages", label: "Messages", icon: "chat", messages: true },
      { to: "/parametres-compte", label: "Mon compte", icon: "user" },
    ],
  },
];

function useActiveGroup(groups) {
  const location = useLocation();
  for (let g = 0; g < groups.length; g++) {
    for (const item of groups[g].items) {
      const active = item.end
        ? location.pathname === item.to
        : location.pathname === item.to || location.pathname.startsWith(item.to + "/");
      if (active) return g;
    }
  }
  return 0;
}

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [unread, setUnread] = useState(0);
  const role = user?.role;

  const activeGroup = useActiveGroup(CANDIDATE_NAV_GROUPS);
  const activeAdminGroup = useActiveGroup(ADMIN_NAV_GROUPS);
  const [openGroups, setOpenGroups] = useState(() => new Set([activeGroup]));
  useEffect(() => {
    setOpenGroups((prev) => new Set(prev).add(activeGroup));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeGroup]);
  const [openAdminGroups, setOpenAdminGroups] = useState(() => new Set([activeAdminGroup]));
  useEffect(() => {
    setOpenAdminGroups((prev) => new Set(prev).add(activeAdminGroup));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeAdminGroup]);

  useEffect(() => {
    let alive = true;
    const poll = () => {
      api("/messages/unread-count")
        .then((d) => { if (alive) setUnread(d.count); })
        .catch(() => {});
    };
    poll();
    const timer = setInterval(poll, 30000);
    return () => { alive = false; clearInterval(timer); };
  }, []);

  const initials = (user?.full_name || "?")
    .split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase();

  function renderLinks(items) {
    return items.map((item) => (
      <NavLink
        key={item.to}
        to={item.to}
        end={item.end}
        className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
      >
        <Icon d={I[item.icon]} />
        <span>{item.label}</span>
        {item.messages && unread > 0 && (
          <span className="nav-badge">{unread}</span>
        )}
      </NavLink>
    ));
  }

  function renderGroups(groups, openSet, toggle) {
    return groups.map((group, i) => {
      if (group.section === null) {
        return <div key={i} className="nav-group">{renderLinks(group.items)}</div>;
      }
      const isOpen = openSet.has(i);
      return (
        <div className="nav-group" key={i}>
          <button
            type="button"
            className="nav-heading"
            aria-expanded={isOpen}
            onClick={() => toggle(i)}
          >
            <span>{group.section}</span>
            <svg
              className={`nav-chevron${isOpen ? " open" : ""}`}
              width="12" height="12" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.2"
              strokeLinecap="round" strokeLinejoin="round"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
          {isOpen && <div className="nav-group-links">{renderLinks(group.items)}</div>}
        </div>
      );
    });
  }

  function toggleGroup(setter, idx) {
    setter((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">O</span>
          <div>
            <div className="brand-name">OrientSkill <span>AI</span></div>
            <div className="brand-sub">Intelligence professionnelle</div>
          </div>
        </div>

        <nav className="nav">
          {role === "admin"
            ? renderGroups(ADMIN_NAV_GROUPS, openAdminGroups, (i) => toggleGroup(setOpenAdminGroups, i))
            : role === "recruiter"
              ? <div className="nav-group">{renderLinks(RECRUITER_NAV)}</div>
              : renderGroups(CANDIDATE_NAV_GROUPS, openGroups, (i) => toggleGroup(setOpenGroups, i))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <span className="sidebar-avatar">{initials}</span>
            <div className="sidebar-user-name">{user?.full_name}</div>
          </div>
          <button type="button" className="nav-item nav-logout" onClick={() => { logout(); navigate("/login"); }}>
            <Icon d={I.logout} size={16} />
            <span>Déconnexion</span>
          </button>
        </div>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}
