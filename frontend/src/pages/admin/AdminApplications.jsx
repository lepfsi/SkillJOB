import { Fragment, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import {
  STATUS_LABELS,
  STATUS_ORDER,
  fmtDate,
  fmtDateTime,
  statusTone,
} from "../../lib.js";
import Avatar from "../../components/Avatar.jsx";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";

// Suivi de TOUTES les candidatures envoyées via la plateforme.
// L'admin voit : qui a postulé où, par quel canal, avec quels documents.
// Il peut corriger un statut avec un motif obligatoire ; l'arbitrage est
// tracé dans l'historique et visible par le candidat.
// Le journal des candidatures reçues par e-mail est affiché en dessous.

const CHANNEL_LABELS = {
  platform: "Plateforme",
  external: "Externe",
  email: "E-mail",
  "": "Suivie",
};

const INBOUND_STATUS = {
  transmise: "Transmise",
  recue: "Reçue",
  non_routee: "Non routée",
};

const ROUTING_LABELS = {
  reference: "Référence",
  keywords: "Mots-clés",
  titre: "Titre / entreprise",
  "": "Aucun",
};

export default function AdminApplications() {
  const [rows, setRows] = useState(null);
  const [status, setStatus] = useState("");
  const [channel, setChannel] = useState("");
  const [error, setError] = useState("");
  const [inboundRows, setInboundRows] = useState(null);
  const [inboundError, setInboundError] = useState("");
  const [inboundNotice, setInboundNotice] = useState("");
  const [resendingId, setResendingId] = useState(null);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");

  function loadRows() {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (channel) params.set("channel", channel);
    const query = params.toString() ? `?${params}` : "";
    return api(`/admin/applications${query}`).then(
      (data) => setRows(data || [])
    );
  }

  useEffect(() => {
    setError("");
    loadRows().catch((err) => setError(err.detail));
  }, [status, channel]);

  function openArbitration(row) {
    setEditing({ id: row.id, status: row.status, reason: "" });
    setNotice("");
    setError("");
  }

  async function saveArbitration(event) {
    event.preventDefault();
    if (!editing) return;
    const reason = editing.reason.trim();
    if (reason.length < 3) {
      setError("Un motif d'au moins 3 caractères est requis.");
      return;
    }
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const res = await api(`/admin/applications/${editing.id}`, {
        method: "PATCH",
        body: { status: editing.status, reason },
      });
      setNotice(
        `Candidature mise à jour : ${STATUS_LABELS[res.status] || res.status}.`
      );
      setEditing(null);
      await loadRows();
    } catch (err) {
      setError(err.detail);
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    api("/admin/inbound-emails?limit=50")
      .then((data) => setInboundRows(data || []))
      .catch((err) => setInboundError(err.detail));
  }, []);

  async function reloadInbound() {
    try {
      const data = await api("/admin/inbound-emails?limit=50");
      setInboundRows(data || []);
    } catch (err) {
      setInboundError(err.detail);
    }
  }

  async function resendAccess(row) {
    setResendingId(row.id);
    setInboundError("");
    setInboundNotice("");
    try {
      const res = await api(`/admin/inbound-emails/${row.id}/resend-access`, {
        method: "POST",
      });
      if (res.ok) {
        setInboundNotice(`Accès renvoyés à ${row.sender_email}.`);
        await reloadInbound();
      } else {
        setInboundError(res.detail || "Envoi impossible.");
      }
    } catch (err) {
      setInboundError(err.detail || "Envoi impossible.");
    } finally {
      setResendingId(null);
    }
  }

  if (error && !rows) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!rows) {
    return <div className="page"><Loader /></div>;
  }

  const sent = rows.filter((r) => r.submitted_at).length;

  return (
    <div className="page">
      <h1>Suivi des candidatures</h1>
      <p className="page-lead">
        Toutes les candidatures passées par OrientSkill AI : envois directs
        aux recruteurs (canal plateforme), candidatures externes suivies et
        candidatures reçues par e-mail puis transmises à l'entreprise.
      </p>

      <div className="stats-strip">
        <div className="stat-tile">
          <span>Candidatures suivies</span>
          <strong>{rows.length}</strong>
        </div>
        <div className="stat-tile">
          <span>Effectivement envoyées</span>
          <strong>{sent}</strong>
        </div>
      </div>

      <div className="segmented-row">
        {[
          ["", "Toutes"],
          ["envoyee", "Envoyées"],
          ["cv_prepare", "CV préparés"],
          ["entretien", "Entretiens"],
          ["identifiee", "Identifiées"],
        ].map(([value, label]) => (
          <button
            key={value || "all"}
            type="button"
            className={`btn btn-small ${status === value ? "btn-primary" : "btn-outline"}`}
            onClick={() => { setError(""); setStatus(value); }}
          >
            {label}
          </button>
        ))}
        <span className="seg-sep" />
        {[
          ["", "Tous canaux"],
          ["platform", "Plateforme"],
          ["external", "Externe"],
          ["email", "E-mail"],
        ].map(([value, label]) => (
          <button
            key={value || "all-ch"}
            type="button"
            className={`btn btn-small ${channel === value ? "btn-primary" : "btn-outline"}`}
            onClick={() => { setError(""); setChannel(value); }}
          >
            {label}
          </button>
        ))}
      </div>

      <ErrorNote error={error} />
      {notice && <div className="alert alert-success">{notice}</div>}

      {rows.length === 0 ? (
        <Empty title="Aucune candidature">
          <p>Les candidatures suivies et envoyées apparaîtront ici.</p>
        </Empty>
      ) : (
        <div className="table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Candidat</th>
                <th>Offre</th>
                <th>Statut</th>
                <th>Canal</th>
                <th>Postulation</th>
                <th>Documents</th>
                <th>Envoyée le</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <Fragment key={r.id}>
                <tr>
                  <td>
                    <div className="app-candidate">
                      <Avatar
                        name={r.candidate_name}
                        photoUrl={r.candidate_photo_url}
                        className="app-avatar"
                      />
                      <div>
                        <strong>{r.candidate_name}</strong>
                        <br />
                        <span className="muted small">{r.candidate_email}</span>
                      </div>
                    </div>
                  </td>
                  <td>
                    <strong>{r.job_title}</strong>
                    <br />
                    <span className="muted small">{r.job_company}</span>
                  </td>
                  <td>
                    <span className={`apps-status ${statusTone(r.status)}`}>
                      {STATUS_LABELS[r.status] || r.status}
                    </span>
                  </td>
                  <td>
                    {CHANNEL_LABELS[r.apply_channel] || r.apply_channel || "Suivie"}
                  </td>
                  <td>
                    {r.apply_channel === "external" ? (
                      <div className="admin-apply-links">
                        {r.apply_url && (
                          <a
                            className="link-more"
                            href={r.apply_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Site de l'entreprise
                          </a>
                        )}
                        {r.apply_email && (
                          <a className="link-more" href={`mailto:${r.apply_email}`}>
                            {r.apply_email}
                          </a>
                        )}
                        {!r.apply_url && !r.apply_email && (
                          <span className="muted small">Non renseigné</span>
                        )}
                      </div>
                    ) : (
                      <span className="muted small">Sur la plateforme</span>
                    )}
                  </td>
                  <td>
                    {r.document_count > 0
                      ? `${r.document_count} document${r.document_count > 1 ? "s" : ""}`
                      : "Aucun"}
                  </td>
                  <td>
                    {r.submitted_at ? fmtDate(r.submitted_at) : "Pas encore"}
                  </td>
                  <td>
                    <div className="admin-user-actions">
                      <Link
                        className="btn btn-outline btn-small"
                        to={`/opportunites/${r.job_id}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Voir l'offre
                      </Link>
                      <button
                        type="button"
                        className="btn btn-ghost btn-small"
                        onClick={() => openArbitration(r)}
                      >
                        Changer le statut
                      </button>
                    </div>
                  </td>
                </tr>
                {editing?.id === r.id && (
                  <tr className="admin-arbitration-row">
                    <td colSpan={8}>
                      <form className="admin-arbitration" onSubmit={saveArbitration}>
                        <p className="small muted">
                          Statut actuel :{" "}
                          <b>{STATUS_LABELS[r.status] || r.status}</b>. Toute
                          correction est tracée avec votre nom, la date et le
                          motif, et le candidat est notifié.
                        </p>
                        <div className="setting-grid">
                          <label className="field">
                            <span>Nouveau statut</span>
                            <select
                              value={editing.status}
                              onChange={(event) =>
                                setEditing({
                                  ...editing,
                                  status: event.target.value,
                                })
                              }
                            >
                              {STATUS_ORDER.map((value) => (
                                <option key={value} value={value}>
                                  {STATUS_LABELS[value]}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="field">
                            <span>Motif (obligatoire)</span>
                            <input
                              value={editing.reason}
                              onChange={(event) =>
                                setEditing({
                                  ...editing,
                                  reason: event.target.value,
                                })
                              }
                              maxLength={1000}
                              placeholder="Ex. dossier complété après relance du candidat"
                            />
                          </label>
                        </div>
                        <div className="actions-row">
                          <button
                            className="btn btn-primary btn-small"
                            disabled={saving}
                          >
                            {saving ? "Enregistrement…" : "Enregistrer l'arbitrage"}
                          </button>
                          <button
                            type="button"
                            className="btn btn-ghost btn-small"
                            onClick={() => setEditing(null)}
                            disabled={saving}
                          >
                            Annuler
                          </button>
                        </div>
                      </form>
                    </td>
                  </tr>
                )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <section className="dash-card admin-inbound" id="candidatures-email">
        <div className="dash-card-head">
          <h2>Candidatures reçues par e-mail</h2>
          <span className="small muted">
            {inboundRows ? `${inboundRows.length} message(s)` : "Chargement…"}
          </span>
        </div>
        <p className="small muted">
          Messages reçus sur l'adresse interne, routés par référence OS-XXXX,
          puis par mots-clés ou par titre. La candidature est transmise à
          l'entreprise avec les pièces jointes d'origine. Un message non routé
          reste visible ici : il n'est jamais envoyé à la mauvaise entreprise.
        </p>
        <ErrorNote error={inboundError} />
        {inboundNotice && (
          <div className="alert alert-success">{inboundNotice}</div>
        )}
        {!inboundRows ? (
          <Loader />
        ) : inboundRows.length === 0 ? (
          <Empty title="Aucune candidature reçue par e-mail">
            <p>
              Les messages reçus sur l'adresse interne apparaîtront ici après
              la relève IMAP ou l'appel du webhook.
            </p>
          </Empty>
        ) : (
          <div className="table-wrap">
            <table className="admin-table inbound-table">
              <thead>
                <tr>
                  <th>Reçu</th>
                  <th>Expéditeur</th>
                  <th>Offre</th>
                  <th>Routage</th>
                  <th>Transmission</th>
                  <th>Accès</th>
                  <th>Pièces</th>
                  <th>État</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {inboundRows.map((row) => (
                  <tr key={row.id}>
                    <td className="small">
                      {row.created_at ? fmtDateTime(row.created_at) : ""}
                    </td>
                    <td>
                      <strong>{row.sender_name || "Candidat"}</strong>
                      <br />
                      <span className="muted small">{row.sender_email}</span>
                    </td>
                    <td>
                      {row.job_id ? (
                        <Link
                          className="link-more"
                          to={`/opportunites/${row.job_id}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {row.job_title || `Offre ${row.job_id}`}
                        </Link>
                      ) : (
                        <span className="muted small">Non identifiée</span>
                      )}
                      {row.company && (
                        <>
                          <br />
                          <span className="muted small">{row.company}</span>
                        </>
                      )}
                    </td>
                    <td className="small">
                      {ROUTING_LABELS[row.routing] || row.routing || "Aucun"}
                    </td>
                    <td className="small">
                      {row.forwarded_to ? (
                        <>
                          <a
                            className="link-more"
                            href={`mailto:${row.forwarded_to}`}
                          >
                            {row.forwarded_to}
                          </a>
                          <br />
                          <span className={row.forward_email_sent ? "muted" : "text-danger"}>
                            {row.forward_email_sent
                              ? "Envoyée"
                              : "Échec de l'envoi"}
                          </span>
                        </>
                      ) : (
                        <span className="muted">Non transmise</span>
                      )}
                    </td>
                    <td className="small">
                      {row.account_created ? (
                        <>
                          Compte créé
                          <br />
                          <span className={row.access_email_sent ? "muted" : "text-danger"}>
                            {row.access_email_sent
                              ? "Accès envoyés"
                              : "Accès non envoyés"}
                          </span>
                        </>
                      ) : row.user_id ? (
                        "Compte existant"
                      ) : (
                        <span className="muted">Aucun compte</span>
                      )}
                    </td>
                    <td className="small">
                      {row.attachments_count > 0 ? (
                        <span title={row.attachment_names.join(", ")}>
                          {row.attachments_count} fichier
                          {row.attachments_count > 1 ? "s" : ""}
                        </span>
                      ) : (
                        <span className="muted">Aucune</span>
                      )}
                    </td>
                    <td>
                      <span
                        className={`inbound-status inbound-status-${row.status}`}
                        title={row.detail}
                      >
                        {INBOUND_STATUS[row.status] || row.status}
                      </span>
                      {row.detail && row.status === "non_routee" && (
                        <>
                          <br />
                          <span className="muted small inbound-detail">
                            {row.detail}
                          </span>
                        </>
                      )}
                    </td>
                    <td>
                      {row.account_created && (
                        <button
                          type="button"
                          className="btn btn-outline btn-small"
                          onClick={() => resendAccess(row)}
                          disabled={resendingId === row.id}
                        >
                          {resendingId === row.id
                            ? "Envoi…"
                            : "Renvoyer les accès"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
