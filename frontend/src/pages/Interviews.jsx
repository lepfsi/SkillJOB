import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, resourceHref } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { fmtDateTime, plural } from "../lib.js";
import { ArrowIcon } from "../components/icons.jsx";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";

// Entretiens : invitations envoyées depuis une shortlist recruteur.
// La page publique /entretiens/:token fonctionne avec le lien de l'e-mail
// (lecture seule avant connexion) ; répondre exige le compte du candidat
// invité. Le parcours suit trois étapes : invitation, réponse, confirmation.

const STATUS_LABELS = {
  pending: "En attente de votre réponse",
  accepted: "Créneau accepté",
  declined: "Autre créneau demandé",
  refused: "Entretien refusé",
};

const HISTORY_LABELS = {
  invited: "Invitation envoyée",
  accepted: "Créneau accepté par le candidat",
  declined: "Autre créneau demandé par le candidat",
  refused: "Entretien refusé par le candidat",
  request_accepted: "Créneau proposé accepté par le recruteur",
  slot_proposed: "Nouveau créneau proposé par le recruteur",
  request_refused: "Demande refusée par le recruteur",
};

const TIMES = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"];

function pad(value) {
  return String(value).padStart(2, "0");
}

function isoDay(day) {
  return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`;
}

function isoLocal(day, time) {
  return `${isoDay(day)}T${time}:00`;
}

function nextDays(count = 14) {
  const days = [];
  const today = new Date();
  for (let offset = 1; days.length < count; offset += 1) {
    const day = new Date(
      today.getFullYear(),
      today.getMonth(),
      today.getDate() + offset
    );
    if (day.getDay() === 0) continue;
    days.push(day);
  }
  return days;
}

function dayLabel(day) {
  return new Intl.DateTimeFormat("fr-FR", {
    weekday: "short",
    day: "2-digit",
    month: "short",
  }).format(day);
}

function SlotPicker({ value, onChange }) {
  const days = useMemo(() => nextDays(14), []);
  const [dayIndex, setDayIndex] = useState(0);
  const selectedDay = days[dayIndex];

  function toggle(time) {
    const slot = isoLocal(selectedDay, time);
    if (value.includes(slot)) {
      onChange(value.filter((item) => item !== slot));
    } else if (value.length < 5) {
      onChange([...value, slot]);
    }
  }

  return (
    <div className="slot-picker">
      <div className="slot-days" role="list" aria-label="Jours disponibles">
        {days.map((day, index) => (
          <button
            type="button"
            role="listitem"
            key={isoDay(day)}
            className={`slot-day${index === dayIndex ? " is-active" : ""}`}
            onClick={() => setDayIndex(index)}
          >
            <span>{dayLabel(day).split(" ")[0]}</span>
            <strong>{day.getDate()}</strong>
            <small>{dayLabel(day).split(" ")[2]}</small>
          </button>
        ))}
      </div>
      <div className="slot-times" aria-label="Heures disponibles">
        {TIMES.map((time) => {
          const slot = isoLocal(selectedDay, time);
          const active = value.includes(slot);
          return (
            <button
              type="button"
              key={time}
              className={`slot-time${active ? " is-active" : ""}`}
              onClick={() => toggle(time)}
            >
              {time}
            </button>
          );
        })}
      </div>
      {value.length > 0 && (
        <div className="chip-row slot-selected">
          {value.map((slot) => (
            <button
              type="button"
              className="chip slot-chip"
              key={slot}
              onClick={() => onChange(value.filter((item) => item !== slot))}
              title="Retirer ce créneau"
            >
              {fmtDateTime(slot)} ×
            </button>
          ))}
        </div>
      )}
      <p className="small muted">
        Choisissez jusqu'à 5 créneaux. Ils seront transmis au recruteur avec
        votre demande.
      </p>
    </div>
  );
}

function StepIndicator({ step }) {
  const steps = [
    ["invitation", "1. Invitation"],
    ["response", "2. Réponse"],
    ["confirmation", "3. Confirmation"],
  ];
  return (
    <ol className="interview-steps" aria-label="Étapes de l'entretien">
      {steps.map(([key, label]) => (
        <li
          key={key}
          className={
            step === key ? "is-active" : steps.findIndex(([k]) => k === step) > steps.findIndex(([k]) => k === key)
              ? "is-done"
              : ""
          }
        >
          {label}
        </li>
      ))}
    </ol>
  );
}

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
      {invite.requested_slots?.length > 0 && (
        <p className="small muted" style={{ margin: 0 }}>
          Vos créneaux proposés :{" "}
          {invite.requested_slots.map((slot) => fmtDateTime(slot)).join(" · ")}
        </p>
      )}
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

function History({ invite }) {
  if (!invite.history?.length) return null;
  return (
    <div className="invite-history">
      <h3>Historique</h3>
      <ol>
        {invite.history.map((entry, index) => (
          <li key={`${entry.at}-${index}`}>
            <strong>{HISTORY_LABELS[entry.action] || entry.action}</strong>
            <span className="small muted">
              {fmtDateTime(entry.at)}
              {entry.slot_at ? ` · ${fmtDateTime(entry.slot_at)}` : ""}
            </span>
            {entry.note && <p className="small">{entry.note}</p>}
          </li>
        ))}
      </ol>
    </div>
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
  const [step, setStep] = useState("invitation");
  const suggested = params.get("reponse");
  const suggestedDecision =
    suggested === "refus"
      ? "refused"
      : suggested === "autre-creneau" || suggested === "refuse"
        ? "declined"
        : "accepted";
  const [decision, setDecision] = useState(suggestedDecision);
  const [requestedSlots, setRequestedSlots] = useState([]);

  useEffect(() => {
    setError("");
    if (token) {
      api(`/interviews/${token}`)
        .then((row) => {
          setInvite(row);
          setStep(row.status === "pending" ? "invitation" : "confirmation");
        })
        .catch((e) => setError(e.detail));
      return;
    }
    api("/interviews")
      .then((rows) => setList(rows || []))
      .catch((e) => setError(e.detail));
  }, [token]);

  async function respond() {
    setBusy(decision);
    setError("");
    setNotice("");
    try {
      const row = await api(`/interviews/${invite.token}/respond`, {
        method: "POST",
        body: {
          decision,
          note: note.trim(),
          requested_slots: decision === "declined" ? requestedSlots : [],
        },
      });
      setInvite(row);
      setStep("confirmation");
      setNotice(
        decision === "accepted"
          ? "Votre créneau est confirmé. Une confirmation vous est envoyée."
          : decision === "refused"
            ? "Votre refus a été transmis au recruteur."
            : "Votre demande d'autre créneau a été transmise au recruteur."
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
          Invitations reçues, créneaux confirmés, demandes d'autre créneau et
          décisions du recruteur.
        </p>
        {list.length === 0 ? (
          <Empty title="Aucune invitation pour le moment">
            <p>
              Les recruteurs qui vous invitent à un entretien font apparaître
              ici le créneau proposé. Vous pouvez accepter, demander un autre
              créneau ou refuser.
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
  const showNewProposal = invite.status === "pending" && invite.recruiter_responded_at;

  return (
    <div className="page page-narrow">
      <Link className="back-link" to="/entretiens">
        <ArrowIcon direction="left" size={12} /> Tous les entretiens
      </Link>
      <h1>Entretien : {invite.job_title}</h1>
      <StepIndicator step={step} />

      {notice && <div className="alert alert-success">{notice}</div>}
      <ErrorNote error={error} />

      {step === "invitation" && (
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

          <div className="invite-message">
            <h3>Message du recruteur</h3>
            <p style={{ whiteSpace: "pre-line" }}>{invite.message}</p>
          </div>

          {showNewProposal && (
            <div className="alert alert-info">
              Le recruteur vous propose un nouveau créneau. Répondez pour le
              confirmer, demander une autre date ou refuser.
            </div>
          )}

          {invite.status === "pending" && !user && (
            <div className="invite-cta">
              <p>
                Connectez-vous avec le compte du candidat invité pour accepter
                ce créneau, demander un autre créneau ou refuser. Votre place
                est conservée.
              </p>
              <Link
                className="btn btn-primary"
                to={`/login?next=${encodeURIComponent(`/entretiens/${invite.token}`)}`}
              >
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
            <div className="actions-row">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setStep("response")}
              >
                Répondre à l'invitation <ArrowIcon direction="right" size={12} />
              </button>
            </div>
          )}

          <a
            className="btn btn-outline btn-small"
            href={resourceHref(invite.calendar_url)}
          >
            Télécharger le calendrier (.ics)
          </a>
          <p className="small muted">
            Heure du Cameroun (UTC+1). Le fichier se met à jour selon votre
            réponse.
          </p>
          <History invite={invite} />
        </section>
      )}

      {step === "response" && (
        <section className="dash-card invite-card">
          <h2>Votre réponse</h2>
          <p className="small muted">
            Choisissez une option, puis envoyez votre réponse. Rien n'est
            enregistré avant votre clic sur « Envoyer ma réponse ».
          </p>

          {suggested === "accepte" && (
            <p className="small muted">
              Vous avez ouvert le lien « accepter » : confirmez ci-dessous.
            </p>
          )}
          {(suggested === "autre-creneau" || suggested === "refuse") && (
            <p className="small muted">
              Vous avez ouvert le lien « demander un autre créneau » :
              précisez vos disponibilités ci-dessous.
            </p>
          )}
          {suggested === "refus" && (
            <p className="small muted">
              Vous avez ouvert le lien « refuser » : confirmez votre refus
              ci-dessous.
            </p>
          )}

          <div className="interview-choices" role="radiogroup" aria-label="Votre réponse">
            <button
              type="button"
              role="radio"
              aria-checked={decision === "accepted"}
              className={`interview-choice${decision === "accepted" ? " is-active" : ""}`}
              onClick={() => setDecision("accepted")}
            >
              <strong>Accepter ce créneau</strong>
              <span>{fmtDateTime(invite.slot_at)}</span>
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={decision === "declined"}
              className={`interview-choice${decision === "declined" ? " is-active" : ""}`}
              onClick={() => setDecision("declined")}
            >
              <strong>Demander un autre créneau</strong>
              <span>Proposez vos disponibilités</span>
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={decision === "refused"}
              className={`interview-choice${decision === "refused" ? " is-active" : ""}`}
              onClick={() => setDecision("refused")}
            >
              <strong>Refuser l'entretien</strong>
              <span>Le recruteur est informé</span>
            </button>
          </div>

          {decision === "declined" && (
            <SlotPicker value={requestedSlots} onChange={setRequestedSlots} />
          )}

          <label className="field">
            <span>Message pour le recruteur (facultatif)</span>
            <textarea
              rows="3"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={1000}
              placeholder="Ex. je suis disponible mardi après 14 h, ou une précision utile."
            />
          </label>

          {decision === "declined" && requestedSlots.length === 0 && (
            <p className="small muted">
              Ajoutez au moins un créneau pour envoyer votre demande.
            </p>
          )}

          <div className="actions-row">
            <button
              type="button"
              className="btn btn-primary"
              disabled={
                !!busy ||
                (decision === "declined" && requestedSlots.length === 0)
              }
              onClick={respond}
            >
              {busy ? "Envoi…" : "Envoyer ma réponse"}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={!!busy}
              onClick={() => setStep("invitation")}
            >
              Retour à l'invitation
            </button>
          </div>
        </section>
      )}

      {step === "confirmation" && (
        <section className="dash-card invite-card">
          <span className={`invite-badge invite-${invite.status}`}>
            {STATUS_LABELS[invite.status]}
          </span>
          <h2>
            {invite.status === "accepted"
              ? "Entretien confirmé"
              : invite.status === "declined"
                ? "Demande transmise"
                : invite.status === "refused"
                  ? "Refus transmis"
                  : "Nouveau créneau proposé"}
          </h2>

          <ul className="invite-facts">
            <li><span>Poste</span><strong>{invite.job_title}</strong></li>
            <li><span>Entreprise</span><strong>{invite.company}</strong></li>
            <li><span>Créneau</span><strong>{fmtDateTime(invite.slot_at)}</strong></li>
            <li><span>Durée</span><strong>{invite.duration_min} minutes</strong></li>
          </ul>

          {invite.status === "accepted" && (
            <p>
              Votre entretien est confirmé. Le recruteur a reçu votre réponse
              et le calendrier à jour.
            </p>
          )}
          {invite.status === "declined" && (
            <div>
              <p>
                Votre demande d'autre créneau a été transmise au recruteur. Il
                peut accepter un de vos créneaux, vous en proposer un autre ou
                refuser la demande.
              </p>
              {invite.requested_slots?.length > 0 && (
                <div className="chip-row">
                  {invite.requested_slots.map((slot) => (
                    <span className="chip" key={slot}>{fmtDateTime(slot)}</span>
                  ))}
                </div>
              )}
            </div>
          )}
          {invite.status === "refused" && (
            <p>
              Votre refus a été transmis au recruteur. Aucun entretien n'est
              planifié pour cette offre.
            </p>
          )}
          {showNewProposal && (
            <div>
              <p>
                Le recruteur vous propose un nouveau créneau. Vous pouvez
                l'accepter, demander une autre date ou refuser.
              </p>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  setDecision("accepted");
                  setRequestedSlots([]);
                  setStep("response");
                }}
              >
                Répondre à ce nouveau créneau
              </button>
            </div>
          )}

          <div className="actions-row">
            <a
              className="btn btn-outline btn-small"
              href={resourceHref(invite.calendar_url)}
            >
              Télécharger le calendrier (.ics)
            </a>
            <Link className="btn btn-ghost btn-small" to="/entretiens">
              Retour aux entretiens
            </Link>
          </div>
          <History invite={invite} />
        </section>
      )}
    </div>
  );
}
