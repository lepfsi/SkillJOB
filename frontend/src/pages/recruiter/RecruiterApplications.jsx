import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../api/client.js";
import {
  RECRUITER_NEXT, REFUSABLE_STATUSES, STATUS_LABELS, STATUS_ORDER,
  fmtDate, statusTone,
} from "../../lib.js";
import Avatar from "../../components/Avatar.jsx";
import ContactDialog from "../../components/ContactDialog.jsx";
import MatchBadge from "../../components/MatchBadge.jsx";
import VerifiedBadge from "../../components/VerifiedBadge.jsx";
import { Empty, ErrorNote, Loader } from "../../components/ui.jsx";

// Page « Candidatures reçues » : les candidatures sont groupées par offre,
// avec total, nouvelles candidatures, score explicable, filtres et
// pagination. Les actions restent limitées aux transitions autorisées au
// recruteur ; la fiche candidat reste le point d'entrée du profil complet.
const PAGE_SIZE = 5;

function deadlineLabel(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return fmtDate(iso);
}

export default function RecruiterApplications() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [busyApp, setBusyApp] = useState(0);
  const [jobId, setJobId] = useState(searchParams.get("offre") || "");
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [collapsed, setCollapsed] = useState({});
  const [refuseFor, setRefuseFor] = useState(null);
  const [refuseReason, setRefuseReason] = useState("");
  const [contactTarget, setContactTarget] = useState(null);

  useEffect(() => {
    api("/recruiter/jobs").then(setJobs).catch(() => setJobs([]));
  }, []);

  useEffect(() => {
    let alive = true;
    // La recherche est différée pour ne pas interroger le serveur à chaque
    // frappe ; les selects et les dates restent immédiats.
    const timer = setTimeout(async () => {
      setBusy(true);
      setError("");
      try {
        const params = new URLSearchParams();
        params.set("page", String(page));
        params.set("page_size", String(PAGE_SIZE));
        if (jobId) params.set("job_id", jobId);
        if (status) params.set("status", status);
        if (query.trim()) params.set("q", query.trim());
        if (dateFrom) params.set("date_from", dateFrom);
        if (dateTo) params.set("date_to", dateTo);
        const result = await api(
          `/recruiter/applications/grouped?${params.toString()}`
        );
        if (!alive) return;
        if ((result.items || []).length === 0 && page > 1) {
          setPage(1);
          return;
        }
        setData(result);
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
  }, [jobId, status, query, dateFrom, dateTo, page, refresh]);

  async function advanceApplication(app) {
    const next = RECRUITER_NEXT[app.status];
    if (!next) return;
    setBusyApp(app.id);
    setError("");
    setNotice("");
    try {
      await api(`/recruiter/applications/${app.id}`, {
        method: "PATCH",
        body: { status: next },
      });
      setNotice(
        `Candidature de ${app.candidate_name} passée à « ${STATUS_LABELS[next]} ».`
      );
      setRefresh((value) => value + 1);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusyApp(0);
    }
  }

  async function confirmRefusal(app) {
    setBusyApp(app.id);
    setError("");
    setNotice("");
    try {
      await api(`/recruiter/applications/${app.id}`, {
        method: "PATCH",
        body: { status: "refusee", reason: refuseReason.trim() },
      });
      setNotice(`Candidature de ${app.candidate_name} refusée.`);
      setRefuseFor(null);
      setRefuseReason("");
      setRefresh((value) => value + 1);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusyApp(0);
    }
  }

  function resetFilters() {
    setJobId("");
    setStatus("");
    setQuery("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  }

  function toggleGroup(groupJobId) {
    setCollapsed((prev) => ({
      ...prev,
      [groupJobId]: !prev[groupJobId],
    }));
  }

  const hasFilters = Boolean(
    jobId || status || query || dateFrom || dateTo
  );
  const totalPages = data
    ? Math.max(1, Math.ceil(data.total_groups / PAGE_SIZE))
    : 1;
  const items = data?.items || [];

  return (
    <div className="page recruiter-applications-page">
      <h1>Candidatures reçues</h1>
      <p className="page-lead">
        Toutes les candidatures de vos offres, regroupées par poste. Chaque
        offre affiche son total et les nouvelles candidatures à traiter ;
        dépliez la pile pour voir les profils, le score de correspondance et
        les actions autorisées.
      </p>

      {notice && <div className="alert alert-success">{notice}</div>}
      <ErrorNote error={error} />

      <div className="stat-grid recv-stats">
        <div className="stat-card">
          <span className="stat-card-value">
            {data ? data.total_applications : "…"}
          </span>
          <span className="stat-card-label">Candidatures</span>
        </div>
        <div className="stat-card">
          <span className="stat-card-value">
            {data ? data.total_groups : "…"}
          </span>
          <span className="stat-card-label">Offres concernées</span>
        </div>
        <div className="stat-card">
          <span className="stat-card-value">
            {data ? data.total_new : "…"}
          </span>
          <span className="stat-card-label">Nouvelles à traiter</span>
        </div>
        <div className="stat-card">
          <span className="stat-card-value">{totalPages}</span>
          <span className="stat-card-label">Pages d'offres</span>
        </div>
      </div>

      <form
        className="filters recv-filters"
        onSubmit={(event) => event.preventDefault()}
      >
        <label className="field">
          <span>Offre</span>
          <select
            value={jobId}
            onChange={(event) => {
              setJobId(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Toutes les offres</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.title}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Statut</span>
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Tous les statuts</option>
            {STATUS_ORDER.map((value) => (
              <option key={value} value={value}>
                {STATUS_LABELS[value]}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Recherche</span>
          <input
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
            placeholder="Candidat, e-mail ou offre"
          />
        </label>
        <label className="field">
          <span>Du</span>
          <input
            type="date"
            value={dateFrom}
            onChange={(event) => {
              setDateFrom(event.target.value);
              setPage(1);
            }}
          />
        </label>
        <label className="field">
          <span>Au</span>
          <input
            type="date"
            value={dateTo}
            onChange={(event) => {
              setDateTo(event.target.value);
              setPage(1);
            }}
          />
        </label>
        {hasFilters && (
          <button
            type="button"
            className="btn btn-ghost btn-small recv-reset"
            onClick={resetFilters}
          >
            Réinitialiser
          </button>
        )}
      </form>

      {busy && <p className="small muted">Mise à jour des candidatures…</p>}
      {!data && busy && <Loader />}
      {data && items.length === 0 && (
        <Empty title="Aucune candidature dans cette vue">
          <p>
            {hasFilters
              ? "Aucune candidature ne correspond à ces filtres. Élargissez la recherche ou réinitialisez les filtres."
              : "Les candidatures envoyées à vos offres apparaîtront ici, regroupées par poste."}
          </p>
        </Empty>
      )}

      {items.map((group) => {
        const isCollapsed = Boolean(collapsed[group.job_id]);
        return (
          <section className="recv-group" key={group.job_id}>
            <header className="recv-group-head">
              <div className="recv-group-title">
                <h2>{group.job_title}</h2>
                {group.new_count > 0 && (
                  <span className="badge badge-medium">
                    {group.new_count} nouvelle
                    {group.new_count > 1 ? "s" : ""}
                  </span>
                )}
              </div>
              <p className="job-meta recv-group-meta">
                {group.job_location || "Lieu non précisé"}
                {group.job_contract_type
                  ? ` · ${group.job_contract_type}`
                  : ""}
                {group.job_deadline
                  ? ` · Date limite : ${deadlineLabel(group.job_deadline)}`
                  : ""}
              </p>
              <div className="recv-group-actions">
                <span className="small muted">
                  {group.total} candidature{group.total > 1 ? "s" : ""}
                  {group.latest_at
                    ? ` · dernière le ${fmtDate(group.latest_at)}`
                    : ""}
                </span>
                <button
                  type="button"
                  className="btn btn-outline btn-small"
                  onClick={() => toggleGroup(group.job_id)}
                >
                  {isCollapsed ? "Déplier" : "Replier"}
                </button>
              </div>
            </header>

            {!isCollapsed && (
              <div className="recv-stack">
                {group.applications.length === 0 && (
                  <p className="muted">
                    Aucune candidature pour cette offre avec ces filtres.
                  </p>
                )}
                {group.applications.map((app) => {
                  const isBusy = busyApp === app.id;
                  const next = RECRUITER_NEXT[app.status];
                  return (
                    <article className="recv-app" key={app.id}>
                      <div className="recv-app-head">
                        <div className="app-candidate">
                          <Avatar
                            name={app.candidate_name}
                            photoUrl={app.candidate_photo_url}
                            className="app-avatar"
                          />
                          <div>
                            <strong>{app.candidate_name}</strong>
                            {app.candidate_verified && (
                              <VerifiedBadge
                                label="Profil vérifié"
                                size={13}
                                className="verified-inline"
                              />
                            )}
                            <p className="job-meta recv-app-meta">
                              {app.candidate_title || "Profil candidat"}
                              {" · "}
                              Candidature du{" "}
                              {fmtDate(app.submitted_at || app.created_at)}
                            </p>
                          </div>
                        </div>
                        <div className="recv-app-badges">
                          <MatchBadge score={app.match_score} />
                          <span
                            className={`apps-status ${statusTone(app.status)}`}
                          >
                            {app.status_label ||
                              STATUS_LABELS[app.status] ||
                              app.status}
                          </span>
                          {app.is_new && (
                            <span className="badge badge-medium">
                              Nouvelle
                            </span>
                          )}
                        </div>
                      </div>

                      {app.cover_note && (
                        <p className="recv-cover">{app.cover_note}</p>
                      )}

                      <div className="recv-app-actions">
                        <Link
                          className="btn btn-ghost btn-small"
                          to={`/recruteur/candidats/${app.candidate_id}`}
                        >
                          Voir la fiche
                        </Link>
                        {next && (
                          <button
                            type="button"
                            className="btn btn-primary btn-small"
                            disabled={isBusy}
                            onClick={() => advanceApplication(app)}
                          >
                            {isBusy
                              ? "Traitement…"
                              : `Passer à « ${STATUS_LABELS[next]} »`}
                          </button>
                        )}
                        {REFUSABLE_STATUSES.has(app.status) && (
                          <button
                            type="button"
                            className="btn btn-remove btn-small"
                            disabled={isBusy}
                            onClick={() => {
                              setRefuseFor(app.id);
                              setRefuseReason("");
                            }}
                          >
                            Refuser
                          </button>
                        )}
                        <button
                          type="button"
                          className="btn btn-outline btn-small"
                          onClick={() =>
                            setContactTarget({
                              user_id: app.candidate_id,
                              full_name: app.candidate_name,
                            })
                          }
                        >
                          Contacter
                        </button>
                        {app.apply_channel === "external" && app.apply_url && (
                          <a
                            className="btn btn-ghost btn-small"
                            href={app.apply_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Offre d'origine
                          </a>
                        )}
                      </div>

                      {refuseFor === app.id && (
                        <form
                          className="app-refuse"
                          onSubmit={(event) => {
                            event.preventDefault();
                            confirmRefusal(app);
                          }}
                        >
                          <label className="field">
                            <span>
                              Motif du refus (facultatif, visible par le
                              candidat)
                            </span>
                            <input
                              value={refuseReason}
                              onChange={(event) =>
                                setRefuseReason(event.target.value)
                              }
                              maxLength={1000}
                              placeholder="Ex. profil incomplet pour le poste"
                            />
                          </label>
                          <div className="actions-row" style={{ marginTop: 0 }}>
                            <button
                              className="btn btn-remove btn-small"
                              disabled={isBusy}
                            >
                              {isBusy ? "Envoi…" : "Confirmer le refus"}
                            </button>
                            <button
                              type="button"
                              className="btn btn-ghost btn-small"
                              disabled={isBusy}
                              onClick={() => {
                                setRefuseFor(null);
                                setRefuseReason("");
                              }}
                            >
                              Annuler
                            </button>
                          </div>
                        </form>
                      )}
                    </article>
                  );
                })}
                {group.total > group.applications.length && (
                  <p className="small muted recv-more">
                    {group.total - group.applications.length} autre
                    {group.total - group.applications.length > 1 ? "s" : ""}{" "}
                    candidature
                    {group.total - group.applications.length > 1 ? "s" : ""}{" "}
                    masquée
                    {group.total - group.applications.length > 1 ? "s" : ""} :
                    affichage limité à 200 par offre.
                  </p>
                )}
              </div>
            )}
          </section>
        );
      })}

      {data && data.total_groups > 0 && (
        <nav className="recv-pagination" aria-label="Pagination des offres">
          <button
            type="button"
            className="btn btn-outline btn-small"
            disabled={page <= 1 || busy}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
          >
            Précédent
          </button>
          <span className="small muted">
            Page {page} sur {totalPages} · {data.total_groups} offre
            {data.total_groups > 1 ? "s" : ""}
          </span>
          <button
            type="button"
            className="btn btn-outline btn-small"
            disabled={!data.has_more || busy}
            onClick={() => setPage((value) => value + 1)}
          >
            Suivant
          </button>
        </nav>
      )}

      {contactTarget && (
        <ContactDialog
          candidate={contactTarget}
          onClose={() => setContactTarget(null)}
        />
      )}
    </div>
  );
}
