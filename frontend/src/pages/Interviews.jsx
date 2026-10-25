import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, resourceHref } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { fmtDateTime, plural } from "../lib.js";
import { Icon, I, ArrowIcon } from "../components/icons.jsx";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";

// Entretiens : invitations envoyées depuis une shortlist recruteur.
// La page publique /entretiens/:token fonctionne avec le lien de l'e-mail
// (lecture seule avant connexion) ; répondre exige le compte du candidat
// invité. Un lien « accepter » ou « autre créneau » présélectionne le
// choix, mais la réponse reste un geste explicite.

const STATUS_LABELS = {
  pending: "En attente de votre réponse",
  accepted: "Créneau accepté",
  declined: "Autre créneau demandé",
};

function InviteCard({ invite }) {
  return (
    <section className="dash-card invite-card">
      <div className="invite-card-head">
        <div>
          <span className={`invite-badge invite-${invite.status}`}>
            {STATUS_LABELS[invite.status]}
          </span>
          <h2>{invite.job_title}</h2>
          <p className="muted" style={{ margin: 0 }}>{invite.company}</p>
        </div>
        <Link className="btn btn-outline btn-small" to={`/entretiens/${invite.token}`}>
          Voir l'invitation <ArrowIcon direction="right" size={12} />
        </Link>
      </div>
      <ul className="invite-facts">
        <li><span>Créneau proposé</span><strong>{fmtDateTime(invite.slot_at)}</strong></li>
        <li><span>Durée</span><strong>{invite.duration_min} minutes</strong></li>
        <li><span>Recruteur</span><strong>{invite.recruiter_name}</strong></li>
      </ul>
      <div className="actions-row">
        <a
          className="btn btn-ghost btn-small"
          href={resourceHref(invite.calendar_url)}
        >
          Calendrier (.ics)
        </a>
      </div>
      {invite.candidate_note && (
        <p className="small muted" style={{ margin: 0 }}>
          Votre message : « {invite.candidate_note} »
        </p>
      )}
    </section>
  );
}

export default function Interviews() {
  const { token } = useParams();
  const { user } = useAuth();
  const [params] = useSearchParams();
  const [invite, setInvite] = useState(null);
  const [list, setList] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");

  const suggested = params.get("reponse"); // accepte | refuse

  useEffect(() => {
    setError("");
    if (token) {
      api(`/interviews/${token}`)
        .then(setInvite)
        .catch((e) => setError(e.detail));
      return;
    }
    api("/interviews")
      .then((rows) => setList(rows || []))
      .catch((e) => setError(e.detail));
  }, [token]);

  async function respond(decision) {
    setBusy(decision);
    setError("");
    setNotice("");
    try {
      const row = await api(`/interviews/${invite.token}/respond`, {
        method: "POST",
        body: { decision, note: note.trim() },
      });
      setInvite(row);
      setNotice(
        decision === "accepted"
          ? "Créneau confirmé. Le recruteur a reçu votre réponse dans sa messagerie."
          : "Votre demande d'un autre créneau est envoyée au recruteur."
      );
      setNote("");
    } catch (err) {
      setError(err.detail || "Réponse impossible");
    } finally {
      setBusy("");
    }
  }

  if (error && !invite && !list) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }

  if (!token) {
    if (!list) return <div className="page"><Loader /></div>;
    return (
      <div className="page">
        <h1>Entretiens</h1>
        <p className="page-lead">
          Invitations reçues, créneaux confirmés et demandes d'autre créneau.
        </p>
        {list.length === 0 ? (
          <Empty title="Aucune invitation pour le moment">
            <p>
              Les recruteurs qui vous invitent à un entretien font apparaître
              ici le créneau proposé. Vous pouvez accepter ou demander un
              autre créneau.
            </p>
            <Link className="btn btn-outline btn-small" to="/candidatures">
              Voir mes candidatures <ArrowIcon direction="right" size={12} />
            </Link>
          </Empty>
        ) : (
          <>
            <p className="small muted">
              {list.length} invitation{plural(list.length, "", "s")} reçue{plural(list.length, "", "s")}.
            </p>
            {list.map((row) => <InviteCard key={row.id} invite={row} />)}
          </>
        )}
      </div>
    );
  }

  if (!invite) return <div className="page"><Loader /></div>;

  const isOwner = user && user.id === invite.candidate_id;
  const canRespond = isOwner && invite.status === "pending";

  return (
    <div className="page page-narrow">
      <Link className="back-link" to="/entretiens">
        <ArrowIcon direction="left" size={12} /> Tous les entretiens
      </Link>
      <h1>Invitation à un entretien</h1>

      {notice && <div className="alert alert-success">{notice}</div>}
      <ErrorNote error={error} />

      <section className="dash-card invite-card">
        <div className="invite-card-head">
          <div>
            <span className={`invite-badge invite-${invite.status}`}>
              {STATUS_LABELS[invite.status]}
            </span>
            <h2>{invite.job_title}</h2>
            <p className="muted" style={{ margin: 0 }}>
              {invite.company}
              {invite.recruiter_name ? ` · ${invite.recruiter_name}` : ""}
            </p>
          </div>
        </div>

        <ul className="invite-facts">
          <li><span>Créneau proposé</span><strong>{fmtDateTime(invite.slot_at)}</strong></li>
          <li><span>Durée</span><strong>{invite.duration_min} minutes</strong></li>
          <li><span>Poste</span><strong>{invite.job_title}</strong></li>
        </ul>

        <div className="actions-row">
          <a
            className="btn btn-outline btn-small"
            href={resourceHref(invite.calendar_url)}
          >
            Télécharger le calendrier (.ics)
          </a>
          <span className="small muted">
            Heure du Cameroun (UTC+1). Le fichier se met à jour selon votre
            réponse.
          </span>
        </div>

        <div className="invite-message">
          <h3>Message du recruteur</h3>
          <p style={{ whiteSpace: "pre-line" }}>{invite.message}</p>
        </div>

        {invite.candidate_note && (
          <div className="invite-message">
            <h3>Votre réponse</h3>
            <p style={{ whiteSpace: "pre-line" }}>{invite.candidate_note}</p>
          </div>
        )}

        {invite.status === "pending" && !user && (
          <div className="invite-cta">
            <p>
              Connectez-vous avec le compte du candidat invité pour accepter
              ce créneau ou demander un autre créneau. Votre place est
              conservée.
            </p>
            <Link className="btn btn-primary" to="/login">
              Se connecter pour répondre <ArrowIcon direction="right" size={12} />
            </Link>
          </div>
        )}

        {invite.status === "pending" && user && !isOwner && (
          <div className="alert alert-error">
            Cette invitation a été adressée à un autre candidat : seul le
            destinataire peut y répondre.
          </div>
        )}

        {canRespond && (
          <div className="invite-cta">
            {suggested === "accepte" && (
              <p className="small muted">
                Vous avez ouvert le lien « accepter » : confirmez ci-dessous.
              </p>
            )}
            {suggested === "refuse" && (
              <p className="small muted">
                Vous avez ouvert le lien « demander un autre créneau » :
                précisez vos disponibilités ci-dessous.
              </p>
            )}
            <label className="field">
              <span>Message pour le recruteur (facultatif)</span>
              <textarea
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={1000}
                placeholder="Ex. je suis disponible mardi après 14 h, ou une précision utile."
              />
            </label>
            <div className="actions-row" style={{ marginTop: "0.7rem" }}>
              <button
                type="button"
                className={`btn btn-primary${suggested === "accepte" ? " invite-choice-focus" : ""}`}
                disabled={!!busy}
                onClick={() => respond("accepted")}
              >
                {busy === "accepted" ? "Confirmation…" : "Accepter ce créneau"}
              </button>
              <button
                type="button"
                className={`btn btn-outline${suggested === "refuse" ? " invite-choice-focus" : ""}`}
                disabled={!!busy}
                onClick={() => respond("declined")}
              >
                {busy === "declined" ? "Envoi…" : "Demander un autre créneau"}
              </button>
            </div>
          </div>
        )}

        {invite.status !== "pending" && (
          <p className="small muted" style={{ marginBottom: 0 }}>
            Cette invitation a reçu une réponse : le recruteur en a été
            informé dans sa messagerie.
          </p>
        )}
      </section>
    </div>
  );
}
