import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext.jsx";
import { api } from "../../api/client.js";
import { Loader, ErrorNote } from "../../components/ui.jsx";

// Catalogue des connecteurs : ce qui est opérationnel, configurable,
// et ce qui relève de la roadmap V2/V3 (§56-57, §76). Formalisation
// honnête : jamais de fonctionnalité simulée présentée comme active.

const KIND_LABELS = {
  llm: "Moteur IA",
  smtp: "Notifications",
  messaging: "Messagerie",
  jobs: "Collecte d'offres",
  credentials: "Vérification",
  data: "Données",
};

const STATUS_LABELS = {
  operationnel: "Opérationnel",
  configure: "À configurer",
  roadmap: "Roadmap",
};

// Raccourcis vers l'écran qui permet d'agir sur chaque connecteur.
const CONNECTOR_ACTIONS = {
  llm: { to: "/admin/parametres", label: "Configurer le moteur IA" },
  smtp: { to: "/admin/parametres", label: "Configurer les e-mails" },
  telegram: { to: "/admin/parametres", label: "Configurer Telegram" },
  whatsapp: { to: "/admin/parametres", label: "Configurer WhatsApp" },
  linkedin: { to: "/admin/sources", label: "Voir les sources" },
  multi_source: { to: "/admin/sources", label: "Voir les sources" },
  skill_graph: { to: "/admin/skill-graph", label: "Ouvrir le Skill Graph" },
};

export default function AdminConnecteurs() {
  const { user } = useAuth();
  const [connectors, setConnectors] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/admin/connectors").then(setConnectors).catch((e) => setError(e.detail));
  }, []);

  if (user && user.role !== "admin") return <Navigate to="/" replace />;
  if (error) return <div className="page"><ErrorNote error={error} /></div>;
  if (!connectors) return <div className="page"><Loader /></div>;

  const operational = connectors.filter((c) => c.status === "operationnel");
  const configurable = connectors.filter((c) => c.status === "configure");
  const roadmap = connectors.filter((c) => c.status === "roadmap");

  const renderGroup = (list) =>
    list.map((c) => {
      const action = CONNECTOR_ACTIONS[c.id];
      return (
        <div className="panel" key={c.id}>
          <div className="section-head">
            <h2 style={{ margin: 0 }}>{c.name}</h2>
            <span className={`connector-status connector-${c.status}`}>
              {STATUS_LABELS[c.status]}
            </span>
          </div>
          <p className="small muted">
            {KIND_LABELS[c.kind] || c.kind} · phase {c.phase}
          </p>
          <p>{c.description}</p>
          {action && (
            <div className="actions-row" style={{ marginTop: "0.5rem" }}>
              <Link className="btn btn-outline btn-small" to={action.to}>
                {action.label}
              </Link>
            </div>
          )}
        </div>
      );
    });

  return (
    <div className="page">
      <h1>Connecteurs</h1>
      <p className="page-lead">
        État réel de chaque intégration. La plateforme distingue
        explicitement ce qui fonctionne aujourd'hui de ce qui appartient à
        la roadmap (formalisation V2/V3 : docs/ROADMAP_V2_V3.md).
      </p>

      <section className="section">
        <h2>Opérationnels</h2>
        {operational.length > 0 ? renderGroup(operational) : (
          <p className="muted">Aucun connecteur actif pour l'instant.</p>
        )}
      </section>

      <section className="section">
        <h2>À configurer</h2>
        {configurable.length > 0 ? renderGroup(configurable) : (
          <p className="muted">Rien à configurer : tout est en place.</p>
        )}
      </section>

      <section className="section">
        <h2>Roadmap V2 / V3</h2>
        {renderGroup(roadmap)}
        <p className="small muted">
          Ces intégrations (LinkedIn via mécanismes autorisés, collecte
          multi-source, Skill Graph national, vérification de credentials)
          sont formalisées dans le document de roadmap : architecture,
          contrats, conformité et critères d'acceptation.
        </p>
      </section>
    </div>
  );
}
