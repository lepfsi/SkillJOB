import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { fmtDate } from "../../lib.js";
import { Loader, ErrorNote } from "../../components/ui.jsx";

// Vue admin sur TOUS les comptes : rôle, MFA, vérification, activité.
// Action sensible : réinitialisation MFA (cas extrême, §45).
export default function AdminUsers() {
  const [users, setUsers] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

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

  if (error && !users) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!users) {
    return <div className="page"><Loader /></div>;
  }

  return (
    <div className="page">
      <h1>Utilisateurs</h1>
      <p className="page-lead">
        Vue complète des comptes : {users.length} utilisateur(s).
      </p>
      {notice && <div className="alert alert-success">{notice}</div>}
      <ErrorNote error={error} />

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
            {users.map((u) => (
              <tr key={u.id}>
                <td>
                  <strong>{u.full_name}</strong>
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
                      : <span className="badge badge-none">—</span>}
                </td>
                <td>{u.has_profile ? "Construit" : "—"}</td>
                <td className="small">
                  {u.applications_count} candidature(s)
                  <br />
                  {u.documents_count} document(s)
                </td>
                <td>
                  {u.mfa_enabled && (
                    <button className="btn btn-remove btn-small" onClick={() => resetMfa(u)}>
                      Réinitialiser MFA
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
