import { useEffect, useState } from "react";
import { Link, Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../../context/AuthContext.jsx";
import { api } from "../../api/client.js";
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

  const CELLS = stats
    ? [
        ["Utilisateurs", stats.users],
        ["Profils construits", stats.profiles],
        ["Offres en base", stats.jobs],
        ["Candidatures", stats.applications],
        ["Documents générés", stats.documents],
        ["Ressources learning", stats.learning_resources],
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
            {CELLS.map(([label, value]) => (
              <div className="stat-cell" key={label}>
                <strong>{value}</strong>
                <span>{label}</span>
              </div>
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
              <Outlet />
            </div>
          </div>

          <div className="panel">
            <h2>Raccourcis</h2>
            <div className="actions-row">
              <Link className="btn btn-ghost" to="/admin/connecteurs">Connecteurs et roadmap</Link>
              <a
                className="btn btn-ghost"
                href="http://localhost:8000/docs"
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
