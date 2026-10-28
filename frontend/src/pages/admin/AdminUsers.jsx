import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import { fmtDate } from "../../lib.js";
import { Loader, ErrorNote } from "../../components/ui.jsx";

// Vue admin sur TOUS les comptes : rôle, MFA, vérification, activité.
// Action sensible : réinitialisation MFA (cas extrême, §45).
export default function AdminUsers() {
  const [users, setUsers] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [role, setRole] = useState("");

  const reload = () => {
    api("/admin/users").then(setUsers).catch((e) => setError(e.detail));
  };

  useEffect(() => {
    reload();
  }, []);

  async function resetMfa(user) {
    if (!window.confirm(
      `Réinitialiser le MFA de ${user.full_name} ? À n'utiliser que si la personne a perdu son application ET ses codes de récupération.`
    )) {
      return;
    }
    try {
      const res = await api(`/admin/users/${user.id}/mfa`, { method: "DELETE" });
      setNotice(res.detail || "MFA réinitialisé.");
      reload();
    } catch (err) {
      setError(err.detail);
    }
  }

  async function banUser(user) {
    const reason = window.prompt(
      `Motif de la suspension de ${user.full_name} (communiqué à l'utilisateur à la connexion, 5 caractères minimum) :`
    );
    if (reason === null) return;
    try {
      const res = await api(`/admin/users/${user.id}/ban`, {
        method: "PUT",
        body: { reason },
      });
      setNotice(res.detail || "Compte suspendu.");
      setError("");
      reload();
    } catch (err) {
      setError(err.detail);
    }
  }

  async function unbanUser(user) {
    if (!window.confirm(
      `Lever la suspension de ${user.full_name} ? La personne pourra se reconnecter.`
    )) {
      return;
    }
    try {
      const res = await api(`/admin/users/${user.id}/ban`, { method: "DELETE" });
      setNotice(res.detail || "Suspension levée.");
      setError("");
      reload();
    } catch (err) {
      setError(err.detail);
    }
  }

  if (error && !users) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!users) {
    return <div className="page"><Loader /></div>;
  }

  const needle = query.trim().toLowerCase();
  const visible = users.filter((u) => {
    if (role && u.role !== role) return false;
    if (!needle) return true;
    return [
      u.full_name, u.email, u.city, u.department, u.region,
    ].filter(Boolean).join(" ").toLowerCase().includes(needle);
  });

  return (
    <div className="page">
      <h1>Utilisateurs</h1>
      <p className="page-lead">
        Vue complète des comptes : {visible.length} sur {users.length} utilisateur(s).
      </p>
      {notice && <div className="alert alert-success">{notice}</div>}
      <ErrorNote error={error} />

      <div className="alert alert-info appeal-link-banner">
        Les contestations de suspension sont instruites dans la page dédiée.{" "}
        <Link to="/admin/recours">Ouvrir les recours</Link>.
      </div>

      <div className="filters">
        <label className="field">
          <span>Rechercher</span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Nom, e-mail, ville…"
          />
        </label>
        <label className="field">
          <span>Rôle</span>
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="">Tous les rôles</option>
            <option value="candidate">Candidats</option>
            <option value="recruiter">Recruteurs</option>
            <option value="admin">Administrateurs</option>
          </select>
        </label>
        {(query || role) && (
          <button
            type="button"
            className="btn btn-ghost btn-small"
            style={{ alignSelf: "end" }}
            onClick={() => { setQuery(""); setRole(""); }}
          >
            Réinitialiser
          </button>
        )}
      </div>

      <div className="table-wrap" style={{ marginTop: "1rem" }}>
        <table className="skills">
          <thead>
            <tr>
              <th>Utilisateur</th>
              <th>Rôle</th>
              <th>Localisation</th>
              <th>MFA</th>
              <th>Vérification</th>
              <th>Profil</th>
              <th>Activité</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {visible.map((u) => (
              <tr key={u.id} className={u.is_banned ? "user-row-banned" : undefined}>
                <td>
                  <strong>{u.full_name}</strong>
                  {u.is_banned && (
                    <span className="badge badge-none" title={u.ban_reason || ""} style={{ marginLeft: "0.45rem" }}>
                      Suspendu
                    </span>
                  )}
                  <div className="small muted">{u.email}</div>
                  <div className="small muted">Inscrit le {fmtDate(u.created_at)}</div>
                </td>
                <td>
                  {u.role === "admin" ? "Administrateur" : u.role === "recruiter" ? "Recruteur" : "Candidat"}
                </td>
                <td className="small">
                  {u.city || ""}{u.city && (u.department || u.region) ? " · " : ""}{u.department || ""}{u.region ? ` (${u.region})` : ""}
                </td>
                <td>
                  {u.mfa_enabled
                    ? <span className="badge badge-strong">Actif</span>
                    : <span className="badge badge-none">Non</span>}
                </td>
                <td>
                  {u.verification_status === "verified"
                    ? <span className="badge badge-strong">Vérifié</span>
                    : u.verification_status === "pending"
                      ? <span className="badge badge-medium">En examen</span>
                      : <span className="badge badge-none">Non renseigné</span>}
                </td>
                <td>{u.has_profile ? "Construit" : "Aucun"}</td>
                <td className="small">
                  {u.applications_count} candidature(s)
                  <br />
                  {u.documents_count} document(s)
                </td>
                <td>
                  <div className="admin-user-actions">
                    {u.role !== "admin" && (
                      u.is_banned ? (
                        <button className="btn btn-outline btn-small" onClick={() => unbanUser(u)}>
                          Lever la suspension
                        </button>
                      ) : (
                        <button className="btn btn-remove btn-small" onClick={() => banUser(u)}>
                          Suspendre
                        </button>
                      )
                    )}
                    {u.mfa_enabled && (
                      <button className="btn btn-ghost btn-small" onClick={() => resetMfa(u)}>
                        Réinitialiser MFA
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td colSpan="8" className="small muted">
                  Aucun compte ne correspond à ces critères.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
