import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client.js";
import { RESOURCE_TYPE_LABELS, fmtDate, plural, EVIDENCE_KIND_LABELS } from "../lib.js";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";
import { Icon, I, ArrowIcon } from "../components/icons.jsx";
import AssistantChat from "../components/AssistantChat.jsx";
import AgentSideCard from "../components/AgentSideCard.jsx";

// Learning (§19, §34) : trois blocs :
//
// 1. « À apprendre maintenant / perfectionner / ensuite » : des ressources
//    RÉELLES, chacune annonçant ce que son lien ouvre (formation exacte,
//    catalogue, résultats de recherche, centre sur place, activité guidée) ;
// 2. « Mes formations suivies » : le parcours du jeune : il ouvre la
//    formation, déclare son avancement, fournit sa PIÈCE (certificat,
//    attestation, badge, portfolio) et décide de la rattacher à son profil ;
// 3. « Progression vérifiable » : chaque compétence avec ses preuves.
//
// Rien n'est inventé (§47) : la pièce est déclarée avec sa référence, et
// seule la validation du candidat la fait entrer dans le profil.

const LEARN_SUGGESTIONS = [
  "Quelle formation suivre en priorité ?",
  "Comment une formation devient une preuve ?",
  "Quelles compétences me manquent ?",
  "Prépare mon entretien",
];

const STATUS_TONE = {
  commencee: "open",
  en_cours: "wait",
  terminee: "ok",
};

function keyOf(skill, title) {
  return `${skill}||${title}`;
}

// ------------------------------------------------------------------ briques

function LinkKindBadge({ resource }) {
  const kind = resource.link_kind;
  return (
    <span className={`learn-kind learn-kind-${kind}`}>
      {resource.link_kind_label || "Lien"}
    </span>
  );
}

function Stepper({ statuses, current }) {
  const index = statuses.findIndex((s) => s.value === current);
  return (
    <ol className="learn-steps" aria-label="Avancement de la formation">
      {statuses.map((step, i) => {
        const state = i < index ? "done" : i === index ? "current" : "todo";
        return (
          <li className={`learn-step ${state}`} key={step.value}>
            <span className="learn-step-dot" />
            <span className="learn-step-label">{step.label}</span>
          </li>
        );
      })}
    </ol>
  );
}

function ProofBox({ enrollment, onOpen }) {
  const bureau = /^https?:\/\//i.test(enrollment.proof_reference || "");
  return (
    <div className="learn-proof">
      <span className="learn-proof-icon"><Icon d={I.shield} size={15} /></span>
      <div>
        <strong>{enrollment.proof_label}</strong>
        <p className="learn-proof-ref">
          {enrollment.proof_reference
            ? (bureau
              ? (
                <a href={enrollment.proof_reference} target="_blank" rel="noreferrer">
                  {enrollment.proof_reference}
                </a>
              )
              : enrollment.proof_reference)
            : "Référence non fournie"}
        </p>
        {enrollment.proof_note && <p className="learn-proof-note">{enrollment.proof_note}</p>}
      </div>
      <button type="button" className="btn btn-ghost btn-small" onClick={onOpen}>
        Modifier
      </button>
    </div>
  );
}

function EnrollmentCard({ enrollment, plan, onPatch, onToProfile, onDelete, busy }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    proof_kind: enrollment.proof_kind,
    proof_reference: enrollment.proof_reference,
    proof_note: enrollment.proof_note,
  });
  const statuses = plan.statuses || [];
  const nextStep = statuses[statuses.findIndex((s) => s.value === enrollment.status) + 1];

  return (
    <article className="learn-follow" id={`suivi-${enrollment.id}`}>
      <header className="learn-follow-head">
        <div className="learn-follow-main">
          <span className="learn-follow-skill">{enrollment.skill}</span>
          <h3>{enrollment.title}</h3>
          <p className="learn-follow-meta">
            {enrollment.provider || "Fournisseur non précisé"}
            {" · "}
            {RESOURCE_TYPE_LABELS[enrollment.kind] || enrollment.kind}
            {" · "}
            <span className="learn-kind-inline">{enrollment.link_kind_label}</span>
            {enrollment.started_at ? ` · ouverte le ${fmtDate(enrollment.started_at)}` : ""}
            {enrollment.completed_at ? ` · terminée le ${fmtDate(enrollment.completed_at)}` : ""}
          </p>
        </div>
        <span className={`learn-status ${STATUS_TONE[enrollment.status] || "open"}`}>
          {enrollment.status_label}
        </span>
      </header>

      <Stepper statuses={statuses} current={enrollment.status} />

      {enrollment.verifiable && !editing ? (
        <ProofBox enrollment={enrollment} onOpen={() => setEditing(true)} />
      ) : editing ? (
        <form
          className="learn-form"
          onSubmit={(e) => {
            e.preventDefault();
            onPatch(enrollment, { ...form, status: "terminee" }, () => setEditing(false));
          }}
        >
          <label>
            <span>Pièce fournie par le fournisseur</span>
            <select
              value={form.proof_kind}
              onChange={(e) => setForm({ ...form, proof_kind: e.target.value })}
            >
              {plan.proof_kinds.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Référence vérifiable (lien du certificat, n° de badge, référence)</span>
            <input
              value={form.proof_reference}
              onChange={(e) => setForm({ ...form, proof_reference: e.target.value })}
              placeholder="https://… ou n° du certificat"
            />
          </label>
          <label>
            <span>Précision utile pour le recruteur</span>
            <textarea
              rows={2}
              value={form.proof_note}
              onChange={(e) => setForm({ ...form, proof_note: e.target.value })}
              placeholder="Durée, contenu, projet réalisé…"
            />
          </label>
          <div className="learn-actions">
            <button className="btn btn-primary btn-small" type="submit" disabled={busy}>
              Enregistrer et marquer terminée
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-small"
              onClick={() => setEditing(false)}
            >
              Annuler
            </button>
          </div>
        </form>
      ) : (
        <p className="learn-hint">
          <Icon d={I.clock} size={14} /> Déclarez votre avancement, puis joignez la
          pièce : c'est elle qui rend la formation vérifiable auprès des recruteurs.
        </p>
      )}

      <div className="learn-actions">
        {enrollment.url && (
          <a
            className="btn btn-outline btn-small"
            href={enrollment.url}
            target="_blank"
            rel="noreferrer"
          >
            Ouvrir la formation <ArrowIcon direction="right" size={12} />
          </a>
        )}
        {nextStep && (
          <button
            type="button"
            className="btn btn-outline btn-small"
            disabled={busy}
            onClick={() => onPatch(enrollment, { status: nextStep.value })}
          >
            Marquer « {nextStep.label} »
          </button>
        )}
        {!enrollment.verifiable && (
          <button
            type="button"
            className="btn btn-outline btn-small"
            onClick={() => setEditing(true)}
          >
            {enrollment.proof_kind === "aucune" ? "Ajouter ma pièce" : "Modifier ma pièce"}
          </button>
        )}
        {enrollment.verifiable && !enrollment.added_to_profile && (
          <button
            type="button"
            className="btn btn-accent btn-small"
            disabled={busy}
            onClick={() => onToProfile(enrollment)}
          >
            Ajouter à mon profil
          </button>
        )}
        {enrollment.added_to_profile && (
          <span className="learn-done">
            <Icon d={I.check} size={14} /> Ajoutée à votre profil,{" "}
            <Link to="/profil">la voir</Link>
          </span>
        )}
        <button
          type="button"
          className="btn btn-ghost btn-small learn-remove"
          disabled={busy}
          onClick={() => onDelete(enrollment)}
        >
          Retirer
        </button>
      </div>
    </article>
  );
}

function ResourceRow({ item, resource, enrolled, busy, onOpen }) {
  const uploaded = resource.link_kind === "interne";
  const local = resource.link_kind === "local";
  const busyKey = busy === keyOf(item.skill, resource.title);

  return (
    <li className="learn-res">
      <div className="learn-res-main">
        <div className="learn-res-top">
          <span className="learn-res-title">{resource.title}</span>
          <LinkKindBadge resource={resource} />
        </div>
        <p className="learn-res-meta">
          {resource.provider} · {RESOURCE_TYPE_LABELS[resource.type] || resource.type}
        </p>
      </div>
      {enrolled ? (
        <span className="learn-res-seen">
          <Icon d={I.check} size={13} /> Suivi
        </span>
      ) : (
        <button
          type="button"
          className="btn btn-outline btn-small"
          disabled={busyKey}
          onClick={() => onOpen(item, resource)}
        >
          {busyKey
            ? "…"
            : uploaded
              ? "Je réalise ce projet"
              : local
                ? "Je m'y inscris"
                : "Ouvrir la formation"}
        </button>
      )}
    </li>
  );
}

function PlanCard({ item, plan, enrolledKeys, busy, onOpen }) {
  return (
    <div className="learn-item">
      <div className="learn-item-head">
        <h3>{item.skill}</h3>
        <span className="learn-item-count">
          {item.resources.length} source{plural(item.resources.length, "", "s")}
        </span>
      </div>
      <p className="learn-reason">{item.reason}</p>
      {item.resources.length > 0 ? (
        <ul className="learn-res-list">
          {item.resources.map((r) => (
            <ResourceRow
              key={`${item.skill}-${r.title}`}
              item={item}
              resource={r}
              enrolled={enrolledKeys.has(keyOf(item.skill, r.title))}
              busy={busy}
              onOpen={onOpen}
            />
          ))}
        </ul>
      ) : (
        <p className="learn-hint">Aucune ressource référencée pour cette compétence.</p>
      )}
    </div>
  );
}

// Section de recommandations : on montre l'essentiel, le reste à la demande
// (les écarts du marché peuvent être nombreux ; la page doit rester lisible).
function PlanSection({
  title, icon, note, items, limit, plan, enrolledKeys, busy, onOpen,
}) {
  const [all, setAll] = useState(false);
  const shown = all ? items : items.slice(0, limit);
  const hidden = items.length - limit;
  return (
    <section className="dash-card">
      <div className="dash-card-head">
        <h2><Icon d={icon} size={16} /> {title}</h2>
        <span className="learn-head-note">{note}</span>
      </div>
      {shown.map((item) => (
        <PlanCard
          key={item.skill}
          item={item}
          plan={plan}
          enrolledKeys={enrolledKeys}
          busy={busy}
          onOpen={onOpen}
        />
      ))}
      {hidden > 0 && (
        <button type="button" className="learn-more" onClick={() => setAll(!all)}>
          {all
            ? "Réduire la liste"
            : `Afficher les ${hidden} autre${plural(hidden, "", "s")} compétence${plural(hidden, "", "s")}`}
        </button>
      )}
    </section>
  );
}

function ProgressCard({ p }) {
  return (
    <div className="progress-card">
      <div className="progress-card-head">
        <h3>{p.skill}</h3>
        <span className={`badge ${p.status === "verifiee" ? "badge-strong" : p.status === "en_progression" ? "badge-medium" : "badge-none"}`}>
          {p.status_label}
        </span>
      </div>
      <p className="progress-demand">
        Niveau {p.level} · demandée par {p.demand} offre{plural(p.demand, "", "s")} active{plural(p.demand, "", "s")}
      </p>
      {p.evidences.length > 0 ? (
        <div>
          {p.evidences.map((e, i) => (
            <span key={i} className="evidence-chip">
              {EVIDENCE_KIND_LABELS[e.kind] || e.kind} : {e.label}
            </span>
          ))}
        </div>
      ) : (
        <p className="evidence-empty">Aucune preuve rattachée pour l'instant.</p>
      )}
      <p className="next-step">{p.next_step}</p>
    </div>
  );
}

function TargetedResource({ match, busy, onOpen, onClear }) {
  const { item, resource } = match;
  return (
    <section className="dash-card learn-target" id="formation-ciblee">
      <div className="dash-card-head">
        <h2><Icon d={I.zap} size={16} /> Formation ciblée</h2>
        <Link className="link-more" to="/learning" onClick={onClear}>
          Voir tout le plan
        </Link>
      </div>
      <div className="learn-target-body">
        <div>
          <span className="learn-follow-skill">{item.skill}</span>
          <h3>{resource.title}</h3>
          <p className="learn-res-meta">
            {resource.provider} · {RESOURCE_TYPE_LABELS[resource.type] || resource.type}
            {" · "}
            <LinkKindBadge resource={resource} />
          </p>
          <p className="learn-reason">{item.reason}</p>
        </div>
        <div className="learn-actions">
          <button
            type="button"
            className="btn btn-primary btn-small"
            disabled={busy === keyOf(item.skill, resource.title)}
            onClick={() => onOpen(item, resource)}
          >
            {busy === keyOf(item.skill, resource.title) ? "…" : "Ouvrir la formation"}
          </button>
          {resource.url && (
            <a
              className="btn btn-outline btn-small"
              href={resource.url}
              target="_blank"
              rel="noreferrer"
            >
              Voir la source
            </a>
          )}
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------- page

export default function Learning() {
  const { resourceKey } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [busy, setBusy] = useState("");
  const [showAllProgress, setShowAllProgress] = useState(false);

  async function refresh() {
    const body = await api("/learning");
    setData(body);
    return body;
  }

  useEffect(() => {
    refresh().catch((e) => setError(e.detail));
  }, []);

  // Ouvre la formation (lien réel) ET enregistre le suivi.
  async function openFormation(item, resource) {
    if (resource.url) {
      window.open(resource.url, "_blank", "noopener,noreferrer");
    }
    setBusy(keyOf(item.skill, resource.title));
    setError("");
    try {
      await api("/learning/enrollments", {
        method: "POST",
        body: {
          skill: item.skill,
          title: resource.title,
          provider: resource.provider,
          url: resource.url || null,
          kind: resource.type,
          link_kind: resource.link_kind,
        },
      });
      await refresh();
      setFlash(`« ${resource.title} » a rejoint vos formations suivies.`);
    } catch (e) {
      setError(e.detail);
    } finally {
      setBusy("");
    }
  }

  async function patchEnrollment(enrollment, payload, done) {
    setBusy(`e${enrollment.id}`);
    setError("");
    try {
      await api(`/learning/enrollments/${enrollment.id}`, { method: "PATCH", body: payload });
      await refresh();
      if (done) done();
      if (payload.proof_kind && payload.status === "terminee") {
        setFlash("Pièce enregistrée : la formation est vérifiable.");
      }
    } catch (e) {
      setError(e.detail);
    } finally {
      setBusy("");
    }
  }

  async function toProfile(enrollment) {
    setBusy(`e${enrollment.id}`);
    setError("");
    try {
      await api(`/learning/enrollments/${enrollment.id}/to-profile`, { method: "POST" });
      await refresh();
      setFlash(
        "Formation rattachée à votre profil : elle apparaît désormais comme "
        + "expérience vérifiable, avec sa référence.",
      );
    } catch (e) {
      setError(e.detail);
    } finally {
      setBusy("");
    }
  }

  async function removeEnrollment(enrollment) {
    setBusy(`e${enrollment.id}`);
    setError("");
    try {
      await api(`/learning/enrollments/${enrollment.id}`, { method: "DELETE" });
      await refresh();
      setFlash("Formation retirée de votre suivi.");
    } catch (e) {
      setError(e.detail);
    } finally {
      setBusy("");
    }
  }

  const enrolledKeys = useMemo(
    () => new Set((data?.enrollments || []).map((e) => keyOf(e.skill, e.title))),
    [data],
  );

  // Lien profond /learning/:resourceKey : on retrouve LA ressource exacte
  // dans le plan, même si elle appartient à un bloc replié.
  const targeted = useMemo(() => {
    if (!resourceKey || !data) return null;
    const items = [
      ...(data.learn_now || []),
      ...(data.improve || []),
      ...(data.learn_next || []),
    ];
    for (const item of items) {
      const resource = (item.resources || []).find((r) => r.key === resourceKey);
      if (resource) return { item, resource };
    }
    return null;
  }, [resourceKey, data]);

  useEffect(() => {
    if (!targeted) return;
    const node = document.getElementById("formation-ciblee");
    if (node) node.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [targeted]);

  if (error && !data) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!data) {
    return <div className="page"><Loader /></div>;
  }

  const stats = data.stats || {};
  const enrollments = data.enrollments || [];
  const empty = data.learn_now.length === 0 && data.learn_next.length === 0
    && !(data.improve || []).length;
  const verified = data.progress.filter((p) => p.status === "verifiee").length;
  // La progression peut couvrir beaucoup de compétences : on montre d'abord
  // les plus demandées par le marché, le reste à la demande.
  const PROGRESS_LIMIT = 8;
  const progressShown = showAllProgress
    ? data.progress
    : data.progress.slice(0, PROGRESS_LIMIT);

  const cards = [
    {
      tone: "green", icon: I.book, num: stats.total || 0,
      label: `formation${plural(stats.total || 0, "", "s")} suivie${plural(stats.total || 0, "", "s")}`,
      note: "Ouvertes depuis vos recommandations",
    },
    {
      tone: "violet", icon: I.clock, num: stats.in_progress || 0,
      label: "en cours",
      note: "Commençées ou à terminer",
    },
    {
      tone: "blue", icon: I.award, num: stats.completed || 0,
      label: `terminée${plural(stats.completed || 0, "", "s")}`,
      note: `${stats.verifiable || 0} avec une pièce vérifiable`,
    },
    {
      tone: "orange", icon: I.shield, num: stats.added_to_profile || 0,
      label: "sur votre profil",
      note: "Expériences vérifiables pour les recruteurs",
    },
  ];

  return (
    <div className="page learn-page">
      <div className="dash-columns">
        <div className="dash-col-main">
          {/* ---------- Bandeau ---------- */}
          <section className="home-hero learn-hero">
            <span className="learn-eyebrow">Montée en compétences</span>
            <h1>Learning</h1>
            <p className="learn-hero-lead">
              Des formations réelles, choisies pour vos écarts de compétences,
              et un suivi qui transforme ce que vous apprenez en preuves.
            </p>
            <p className="learn-hero-note">
              Chaque source annonce ce que son lien ouvre : formation exacte,
              catalogue du fournisseur, résultats de recherche, centre de
              formation sur place ou activité guidée. Vous ouvrez la formation,
              vous déclarez votre avancement, vous joignez votre pièce : elle
              devient une expérience vérifiable de votre profil.
            </p>
          </section>

          {/* ---------- Indicateurs réels ---------- */}
          <div className="opps-stats learn-stats">
            {cards.map((card) => (
              <div className={`opps-stat opps-stat-${card.tone}`} key={card.label}>
                <span className="opps-stat-icon"><Icon d={card.icon} size={18} /></span>
                <span className="opps-stat-num">{card.num}</span>
                <span className="opps-stat-label">{card.label}</span>
                <span className="opps-stat-note">{card.note}</span>
              </div>
            ))}
          </div>

          <ErrorNote error={error} />
          {flash && <div className="learn-flash">{flash}</div>}

          {targeted && (
            <TargetedResource
              match={targeted}
              busy={busy}
              onOpen={openFormation}
            />
          )}
          {resourceKey && !targeted && (
            <div className="learn-flash learn-flash-warn">
              Cette formation ne figure plus dans votre plan actuel.{" "}
              <Link to="/learning">Voir toutes les recommandations</Link>.
            </div>
          )}

          {/* ---------- Formations suivies ---------- */}
          {enrollments.length > 0 && (
            <section className="dash-card learn-follows">
              <div className="dash-card-head">
                <h2><Icon d={I.cap} size={16} /> Mes formations suivies</h2>
                <span className="learn-head-note">
                  {stats.verifiable || 0} vérifiable{plural(stats.verifiable || 0, "", "s")} sur {enrollments.length}
                </span>
              </div>
              {enrollments.map((e) => (
                <EnrollmentCard
                  key={e.id}
                  enrollment={e}
                  plan={data}
                  busy={busy === `e${e.id}`}
                  onPatch={patchEnrollment}
                  onToProfile={toProfile}
                  onDelete={removeEnrollment}
                />
              ))}
            </section>
          )}

          {empty && (
            <Empty title="Aucun écart de compétences détecté">
              <p>
                Votre profil couvre les compétences principales des offres
                actuelles, ou votre profil n'est pas encore construit.
              </p>
              <Link className="btn btn-outline" to="/profil">Vérifier mon profil</Link>
            </Empty>
          )}

          {/* ---------- Recommandations ---------- */}
          {data.learn_now.length > 0 && (
            <PlanSection
              title="À apprendre maintenant"
              icon={I.zap}
              note="écarts face à vos métiers recommandés"
              items={data.learn_now}
              limit={4}
              plan={data}
              enrolledKeys={enrolledKeys}
              busy={busy}
              onOpen={openFormation}
            />
          )}

          {(data.improve || []).length > 0 && (
            <PlanSection
              title="Perfectionner mon domaine"
              icon={I.award}
              note="vos acquis, consolidés par des pièces reconnues"
              items={data.improve}
              limit={3}
              plan={data}
              enrolledKeys={enrolledKeys}
              busy={busy}
              onOpen={openFormation}
            />
          )}

          {data.learn_next.length > 0 && (
            <PlanSection
              title="À apprendre ensuite"
              icon={I.layers}
              note="les autres écarts repérés sur le marché"
              items={data.learn_next}
              limit={4}
              plan={data}
              enrolledKeys={enrolledKeys}
              busy={busy}
              onOpen={openFormation}
            />
          )}

          {/* ---------- Progression vérifiable ---------- */}
          {data.progress.length > 0 && (
            <section className="dash-card">
              <div className="dash-card-head">
                <h2><Icon d={I.chart} size={16} /> Progression vérifiable</h2>
                <span className="learn-head-note">
                  {verified} compétence{plural(verified, "", "s")} appuyée{plural(verified, "", "s")} sur {data.progress.length}
                </span>
              </div>
              <p className="learn-reason">
                Une compétence appuyée par des preuves pèse davantage dans le
                matching. Les preuves viennent de votre profil (expériences,
                projets, certifications) et des formations vérifiées ci-dessus.
              </p>
              <div className="progress-grid">
                {progressShown.map((p) => <ProgressCard key={p.skill} p={p} />)}
              </div>
              {data.progress.length > PROGRESS_LIMIT && (
                <button
                  type="button"
                  className="learn-more"
                  onClick={() => setShowAllProgress(!showAllProgress)}
                >
                  {showAllProgress
                    ? "Réduire la liste"
                    : `Afficher les ${data.progress.length - PROGRESS_LIMIT} autres compétences`}
                </button>
              )}
            </section>
          )}

          <AssistantChat compact suggestions={LEARN_SUGGESTIONS} pageContext="Formations" />
        </div>

        {/* ---------- Colonne latérale ---------- */}
        <div className="dash-col-side">
          <AgentSideCard
            page="Formations"
            hint="Ori peut relier vos écarts de compétences aux formations réelles du référentiel."
          />
          <section className="dash-card learn-howto">
            <div className="dash-card-head">
              <h2><Icon d={I.clipboard} size={16} /> Comment ça marche</h2>
            </div>
            <ol className="learn-howto-steps">
              <li>
                <span className="learn-howto-num">1</span>
                <div>
                  <strong>Ouvrez une formation</strong>
                  <p>Le lien mène à la page réelle de la formation que vous allez suivre.</p>
                </div>
              </li>
              <li>
                <span className="learn-howto-num">2</span>
                <div>
                  <strong>Suivez votre avancement</strong>
                  <p>Commençée, en cours, terminée : vous déclarez où vous en êtes.</p>
                </div>
              </li>
              <li>
                <span className="learn-howto-num">3</span>
                <div>
                  <strong>Joignez votre pièce</strong>
                  <p>Certificat, attestation, badge ou portfolio, avec sa référence vérifiable.</p>
                </div>
              </li>
              <li>
                <span className="learn-howto-num">4</span>
                <div>
                  <strong>Validez l'ajout au profil</strong>
                  <p>La formation devient une expérience vérifiable visible par les recruteurs.</p>
                </div>
              </li>
            </ol>
          </section>

          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.link} size={16} /> Nature des liens</h2>
            </div>
            <ul className="learn-legend">
              {(data.link_kinds || []).map((k) => (
                <li key={k.value}>
                  <span className={`learn-kind learn-kind-${k.value}`}>{k.label}</span>
                </li>
              ))}
            </ul>
            <p className="learn-hint">
              Aucun lien ne mène à une page d'accueil trompeuse : quand seule une
              recherche est possible, c'est écrit.
            </p>
          </section>

          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Icon d={I.compass} size={16} /> Aller plus loin</h2>
            </div>
            <ul className="learn-links">
              <li>
                <Link to="/profil">
                  <Icon d={I.user} size={15} /> Mon profil et ses preuves
                </Link>
              </li>
              <li>
                <Link to="/opportunites">
                  <Icon d={I.briefcase} size={15} /> Les offres qui demandent ces compétences
                </Link>
              </li>
              <li>
                <Link to="/carriere">
                  <Icon d={I.compass} size={15} /> Mes métiers recommandés
                </Link>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
