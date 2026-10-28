import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { fmtDate, fmtDateTime } from "../../lib.js";
import { Empty, ErrorNote, Loader } from "../../components/ui.jsx";

// Page dédiée aux recours après suspension : filtres d'instruction,
// contexte du compte, fil des échanges et décision motivée. Accepter lève
// la suspension ; demander un complément laisse le recours ouvert.
const STATUS = {
  pending: { label: "En attente", className: "badge-medium" },
  complement: { label: "Complément attendu", className: "badge-medium" },
  accepted: { label: "Accepté", className: "badge-strong" },
  rejected: { label: "Refusé", className: "badge-none" },
};

const ACTIONS = {
  depot: "Dépôt du recours",
  message: "Message du candidat",
  complement: "Demande de complément",
  accepted: "Recours accepté",
  rejected: "Recours refusé",
};

const ACTORS = {
  candidate: "Candidat",
  admin: "Administration",
};

function ageLabel(hours) {
  if (hours == null || hours < 1) return "moins d'une heure";
  if (hours < 24) return `${Math.floor(hours)} h`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "1 jour" : `${days} jours`;
}

export default function AdminAppeals() {
  const [rows, setRows] = useState(null);
  const [busy, setBusy] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [notes, setNotes] = useState({});
  const [status, setStatus] = useState("open");
  const [kind, setKind] = useState("");
  const [user, setUser] = useState("");
  const [q, setQ] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let alive = true;
    // Léger délai : la recherche par nom ou par texte ne déclenche pas
    // une requête à chaque frappe.
    const timer = setTimeout(async () => {
      setBusy(true);
      setError("");
      try {
        const params = new URLSearchParams();
        if (status) params.set("status", status);
        if (kind) params.set("kind", kind);
        if (user.trim()) params.set("user", user.trim());
        if (q.trim()) params.set("q", q.trim());
        if (dateFrom) params.set("date_from", dateFrom);
        if (dateTo) params.set("date_to", dateTo);
        const data = await api(`/admin/appeals?${params.toString()}`);
        if (alive) setRows(data || []);
      } catch (err) {
        if (alive) setError(err.detail);
      } finally {
        if (alive) setBusy(false);
      }
    }, 220);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [status, kind, user, q, dateFrom, dateTo, refresh]);

  async function decide(row, decision) {
    const note = (notes[row.id] || "").trim();
    if (note.length < 10) {
      setError("Le motif est obligatoire (10 caractères minimum).");
      return;
    }
    setBusyId(row.id);
    setError("");
    setNotice("");
    try {
      await api(`/admin/appeals/${row.id}`, {
        method: "PUT",
        body: { decision, note },
      });
      setNotice(
        decision === "accepted"
          ? `Recours de ${row.user_name} accepté : suspension levée et décision notifiée.`
          : decision === "complement"
            ? `Complément demandé à ${row.user_name} : le recours reste ouvert.`
            : `Recours de ${row.user_name} refusé : décision notifiée.`
      );
      setNotes((prev) => ({ ...prev, [row.id]: "" }));
      setRefresh((value) => value + 1);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusyId(null);
    }
  }

  function resetFilters() {
    setStatus("open");
    setKind("");
    setUser("");
    setQ("");
    setDateFrom("");
    setDateTo("");
  }

  const list = rows || [];
  const pendingCount = list.filter((row) => row.status === "pending").length;
  const complementCount = list.filter(
    (row) => row.status === "complement"
  ).length;
  const closedCount = list.filter((row) => !row.is_open).length;
  const hasFilters = Boolean(
    kind || user || q || dateFrom || dateTo || status !== "open"
  );

  return (
    <div className="page admin-appeals-page">
      <h1>Recours</h1>
      <p className="page-lead">
        Comptes suspendus qui contestent une décision. Chaque recours est
        instruit avec son contexte et son historique ; toute décision est
        motivée, horodatée, notifiée au candidat et tracée dans le journal
        d'administration.
      </p>
      {notice && <div className="alert alert-success">{notice}</div>}
      <ErrorNote error={error} />

      <div className="stat-grid appeal-stats">
        <div className="stat-card">
          <span className="stat-card-value">{list.length}</span>
          <span className="stat-card-label">Recours affichés</span>
        </div>
        <div className="stat-card">
          <span className="stat-card-value">{pendingCount}</span>
          <span className="stat-card-label">En attente d'examen</span>
        </div>
        <div className="stat-card">
          <span className="stat-card-value">{complementCount}</span>
          <span className="stat-card-label">Complément attendu</span>
        </div>
        <div className="stat-card">
          <span className="stat-card-value">{closedCount}</span>
          <span className="stat-card-label">Traités dans la vue</span>
        </div>
      </div>

      <form
        className="filters appeal-filters"
        onSubmit={(event) => event.preventDefault()}
      >
        <label className="field">
          <span>Statut</span>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="open">Ouverts (attente + complément)</option>
            <option value="pending">En attente</option>
            <option value="complement">Complément attendu</option>
            <option value="accepted">Acceptés</option>
            <option value="rejected">Refusés</option>
            <option value="">Tous les recours</option>
          </select>
        </label>
        <label className="field">
          <span>Type</span>
          <select
            value={kind}
            onChange={(event) => setKind(event.target.value)}
          >
            <option value="">Tous les types</option>
            <option value="suspension">Suspension de compte</option>
          </select>
        </label>
        <label className="field">
          <span>Utilisateur</span>
          <input
            type="search"
            value={user}
            onChange={(event) => setUser(event.target.value)}
            placeholder="Nom ou e-mail"
          />
        </label>
        <label className="field">
          <span>Recherche</span>
          <input
            type="search"
            value={q}
            onChange={(event) => setQ(event.target.value)}
            placeholder="Message, motif…"
          />
        </label>
        <label className="field">
          <span>Du</span>
          <input
            type="date"
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
          />
        </label>
        <label className="field">
          <span>Au</span>
          <input
            type="date"
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
          />
        </label>
        {hasFilters && (
          <button
            type="button"
            className="btn btn-ghost btn-small appeal-reset"
            onClick={resetFilters}
          >
            Réinitialiser
          </button>
        )}
      </form>

      {busy && list.length > 0 && (
        <p className="small muted">Mise à jour de la liste…</p>
      )}
      {!rows && busy && <Loader />}
      {rows && list.length === 0 && (
        <Empty title="Aucun recours dans cette vue">
          <p>
            {status === "open"
              ? "Aucun recours ouvert pour le moment : les comptes suspendus peuvent en déposer un depuis l'écran de connexion."
              : "Aucun recours ne correspond à ces filtres."}
          </p>
        </Empty>
      )}

      {list.length > 0 && (
        <ul className="admin-appeal-list">
          {list.map((row) => {
            const state = STATUS[row.status] || {
              label: row.status,
              className: "badge-none",
            };
            const isBusy = busyId === row.id;
            return (
              <li
                key={row.id}
                className={`admin-appeal appeal-status-${row.status}`}
              >
                <div className="admin-appeal-head">
                  <strong>{row.user_name}</strong>
                  <span className="small muted">{row.user_email}</span>
                  <span className={`badge ${state.className}`}>
                    {state.label}
                  </span>
                  <span className="badge badge-none">
                    {row.is_open
                      ? `Ouvert depuis ${ageLabel(row.age_hours)}`
                      : `Traité en ${ageLabel(row.age_hours)}`}
                  </span>
                </div>

                <div className="appeal-context">
                  <span>
                    <b>Type :</b> Suspension de compte
                  </span>
                  <span>
                    <b>Compte :</b>{" "}
                    {row.is_banned ? "Suspendu" : "Actif"}
                  </span>
                  <span>
                    <b>Inscrit le :</b> {fmtDate(row.user_created_at)}
                  </span>
                  <span>
                    <b>Activité :</b> {row.applications_count} candidature(s)
                    {" · "}
                    {row.documents_count} document(s)
                  </span>
                </div>

                <p className="admin-appeal-reason">
                  <b>Motif de la suspension :</b>{" "}
                  {row.ban_reason || "non précisé"}
                </p>
                <blockquote>{row.message}</blockquote>

                {row.history?.length > 0 && (
                  <div className="appeal-history">
                    <h4>Historique des échanges</h4>
                    <ol>
                      {row.history.map((entry, index) => (
                        <li key={`${row.id}-${entry.at}-${index}`}>
                          <div className="appeal-history-head">
                            <span className="appeal-history-date">
                              {fmtDateTime(entry.at)}
                            </span>
                            <span className="appeal-history-action">
                              {ACTIONS[entry.action] || entry.action}
                            </span>
                            <span className="small muted">
                              {ACTORS[entry.actor] || entry.actor}
                              {entry.actor_name
                                ? ` · ${entry.actor_name}`
                                : ""}
                            </span>
                          </div>
                          {entry.note && (
                            <p className="appeal-history-note">{entry.note}</p>
                          )}
                        </li>
                      ))}
                    </ol>
                  </div>
                )}

                {row.is_open ? (
                  <div className="appeal-decision">
                    <label className="field">
                      <span>
                        Motif de la décision (obligatoire, visible par le
                        candidat)
                      </span>
                      <textarea
                        rows={3}
                        value={notes[row.id] || ""}
                        onChange={(event) =>
                          setNotes((prev) => ({
                            ...prev,
                            [row.id]: event.target.value,
                          }))
                        }
                        placeholder="Expliquez la décision : elle sera notifiée au candidat et conservée dans l'historique."
                      />
                    </label>
                    <div className="actions-row">
                      <button
                        type="button"
                        className="btn btn-primary btn-small"
                        disabled={isBusy}
                        onClick={() => decide(row, "accepted")}
                      >
                        {isBusy ? "Traitement…" : "Accepter et lever la suspension"}
                      </button>
                      <button
                        type="button"
                        className="btn btn-outline btn-small"
                        disabled={isBusy}
                        onClick={() => decide(row, "complement")}
                      >
                        Demander un complément
                      </button>
                      <button
                        type="button"
                        className="btn btn-remove btn-small"
                        disabled={isBusy}
                        onClick={() => decide(row, "rejected")}
                      >
                        Refuser le recours
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="appeal-decision-closed">
                    <p>
                      <b>Décision :</b> {state.label}
                      {row.reviewed_by_name
                        ? ` par ${row.reviewed_by_name}`
                        : ""}
                      {row.reviewed_at
                        ? ` le ${fmtDateTime(row.reviewed_at)}`
                        : ""}
                    </p>
                    {row.admin_note && (
                      <p>
                        <b>Motif :</b> {row.admin_note}
                      </p>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
