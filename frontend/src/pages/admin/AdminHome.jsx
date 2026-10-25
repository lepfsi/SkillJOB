import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext.jsx";
import { api, docsHref } from "../../api/client.js";
import { Loader, ErrorNote } from "../../components/ui.jsx";

// Vue générale : statistiques plateforme + état des services.
export default function AdminHome() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/admin/stats").then(setStats).catch((e) => setError(e.detail));
  }, []);

  if (user && user.role !== "admin") return <Navigate to="/" replace />;

  // Chaque indicateur mène à l'écran qui permet de l'expliquer ou d'agir.
  const CELLS = stats
    ? [
        { label: "Utilisateurs", value: stats.users, to: "/admin/utilisateurs" },
        { label: "Profils construits", value: stats.profiles, to: "/admin/utilisateurs" },
        { label: "Offres en base", value: stats.jobs, to: "/admin/offres" },
        { label: "Candidatures", value: stats.applications, to: "/admin/institutionnel" },
        { label: "Documents générés", value: stats.documents, to: "/admin/utilisateurs" },
        { label: "Ressources learning", value: stats.learning_resources },
        {
          label: "Signalements à traiter",
          value: stats.open_reports ?? 0,
          to: "/admin/signalements",
        },
        {
          label: "Suivi des candidatures",
          value: stats.applications,
          to: "/admin/candidatures",
        },
      ]
    : [];

  return (
    <div className="page">
      <h1>Administration</h1>
      <p className="page-lead">
        Console de gestion de la plateforme : contenu, paramètres des
        services et connecteurs.
      </p>
      <ErrorNote error={error} />
      {!stats && !error && <Loader />}

      {stats && (
        <>
          <div className="admin-stats">
            {CELLS.map((cell) => (
              cell.to ? (
                <Link
                  className="stat-cell stat-cell-link"
                  key={cell.label}
                  to={cell.to}
                  title={`Ouvrir : ${cell.label}`}
                >
                  <strong>{cell.value}</strong>
                  <span>{cell.label}</span>
                </Link>
              ) : (
                <div className="stat-cell" key={cell.label}>
                  <strong>{cell.value}</strong>
                  <span>{cell.label}</span>
                </div>
              )
            ))}
          </div>

          <div className="panel">
            <h2>État des services</h2>
            <ul className="trend-list">
              <li>
                <span>Moteur IA (assistant)</span>
                <span className={`trend ${stats.llm_enabled ? "trend-up" : "trend-stable"}`}>
                  {stats.llm_enabled ? "LLM actif" : "Mode règles locales"}
                </span>
              </li>
              <li>
                <span>Notifications e-mail (SMTP)</span>
                <span className={`trend ${stats.smtp_enabled ? "trend-up" : "trend-stable"}`}>
                  {stats.smtp_enabled ? "Configuré" : "Non configuré"}
                </span>
              </li>
            </ul>
            <div className="actions-row">
              <Link className="btn btn-outline" to="/admin/parametres">Configurer les services</Link>
              <Link className="btn btn-ghost" to="/admin/offres">Gérer la base d'offres</Link>
            </div>
          </div>

          <div className="panel">
            <h2>Raccourcis</h2>
            <div className="actions-row">
              <Link className="btn btn-ghost" to="/admin/connecteurs">Connecteurs et roadmap</Link>
              <a
                className="btn btn-ghost"
                href={docsHref()}
                target="_blank"
                rel="noreferrer"
              >
                Documentation API (OpenAPI)
              </a>
            </div>
            <p className="small muted">
              Le compte administrateur pilote les mises à jour de contenu et
              les intégrations (SMTP, LLM, Telegram, WhatsApp) sans toucher au
              code.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
