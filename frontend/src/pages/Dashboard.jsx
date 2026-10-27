import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { Icon, I, ArrowIcon } from "../components/icons.jsx";
import { Loader, ErrorNote } from "../components/ui.jsx";
import Ring from "../components/Ring.jsx";
import VerifiedBadge from "../components/VerifiedBadge.jsx";
import { initialsOf, mapInternalPath, plural } from "../lib.js";

// Accueil (maquette) : l'agent travaille POUR le jeune. Toutes les
// valeurs affichées proviennent de l'API, aucune donnée inventée (§47).
// Là où la maquette montre des chiffres qui n'existent pas dans nos
// données (score détaillé, « +14 points », durées), on les remplace par
// des informations réelles ou on les omet.

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [profile, setProfile] = useState(undefined);
  const [jobs, setJobs] = useState([]);
  const [allJobs, setAllJobs] = useState([]);
  const [apps, setApps] = useState([]);
  const [best, setBest] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/dashboard").then(setData).catch((e) => setError(e.detail));
    api("/profile").then(setProfile).catch(() => setProfile(null));
    api("/jobs?min_score=45&limit=200").then((j) => setJobs(j || [])).catch(() => setJobs([]));
    api("/jobs?limit=200").then((j) => setAllJobs(j || [])).catch(() => setAllJobs([]));
    api("/applications").then((a) => setApps(a || [])).catch(() => setApps([]));
  }, []);

  // Détail de la meilleure piste : score + compétences couvertes / manquantes.
  useEffect(() => {
    if (!data) return;
    const id = data.next_action?.job_id || data.top_matches?.[0]?.id;
    if (!id) return;
    api(`/jobs/${id}`).then(setBest).catch(() => setBest(null));
  }, [data]);

  if (error) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!data || profile === undefined) {
    return <div className="page"><Loader /></div>;
  }

  const firstName = (data.name || "").split(" ")[0];
  const comp = data.profile_completeness;
  const na = data.next_action;
  const bestJob = best?.job || null;
  const bestMatch = best?.match || null;
  const naBase = na?.href
    ? mapInternalPath(na.href)
    : na?.job_id
      ? `/opportunites/${na.job_id}`
      : na?.type === "learn" ? "/learning" : "/opportunites";
  const naTo = na?.type === "adapt_cv" && naBase.startsWith("/opportunites/")
    ? `${naBase}?galerie=cv`
    : naBase;

  // Adéquation moyenne au marché : moyenne réelle des scores sur les offres.
  const scored = allJobs.filter((j) => j.match_score != null);
  const avgScore = scored.length
    ? Math.round(scored.reduce((s, j) => s + j.match_score, 0) / scored.length)
    : null;

  // Meilleure correspondance réelle (détail de l'offre ou top match).
  const bestScore = bestMatch?.score ?? data.top_matches?.[0]?.score ?? null;

  // Compétences réellement en hausse cette semaine (pct_change positif).
  const rising = data.market_trends.filter((t) => t.pct_change > 0).slice(0, 4);

  // Écarts expliqués : chaque compétence prioritaire vient d'un métier
  // recommandé ou d'une offre réelle, avec sa raison affichable.
  const gapDetails = data.skill_gaps || [];
  const gapBySkill = Object.fromEntries(gapDetails.map((g) => [g.skill, g]));

  // ---- Profil absent : inviter à démarrer ----
  if (profile === null) {
    return (
      <div className="page">
        <section className="home-hero">
          <h1>Bonjour {firstName} {data.verified && <VerifiedBadge size={20} />}</h1>
          <p>Chaque grande carrière commence par une bonne orientation.</p>
          <p>OrientSkill AI transforme votre potentiel en opportunités.</p>
        </section>
        <section className="naa">
          <div className="naa-head"><Icon d={I.spark} size={16} /><h2>Commencez ici</h2></div>
          <h3 className="naa-title">Créez votre profil pour activer votre agent</h3>
          <p className="small muted" style={{ marginTop: 0 }}>{data.ai_briefing}</p>
          <div className="naa-actions">
            <Link className="btn btn-primary" to="/onboarding">Importer mon CV</Link>
            <Link className="btn btn-outline" to="/questionnaire">Répondre au questionnaire</Link>
          </div>
        </section>
      </div>
    );
  }

  const coverageTotal = bestMatch
    ? bestMatch.covered.length + bestMatch.partial.length + bestMatch.missing.length
    : 0;

  // Plan de la semaine : chaque action s'appuie sur des données
  // vérifiables (offres actives, demandes réelles, scores, échéances).
  const appliedIds = new Set((apps || []).map((a) => a.job_id));
  const notApplied = jobs.filter((j) => !appliedIds.has(j.id));
  const activeOffers = allJobs.length;

  // Combien d'offres actives demandent réellement cette compétence ?
  const demandOf = (skill) => allJobs.filter((j) =>
    (j.required_skills || []).some((s) =>
      (s.name || "").toLowerCase() === String(skill).toLowerCase())
  ).length;

  const daysUntil = (deadline) =>
    Math.ceil((new Date(deadline) - new Date()) / 86400000);

  const fmtDeadline = (deadline) => new Date(deadline).toLocaleDateString("fr-FR", {
    day: "numeric", month: "long",
  });

  const plan = [];
  // 1) Priorité absolue : une forte correspondance ferme bientôt.
  const urgentJob = notApplied.find((j) =>
    j.deadline
    && (j.match_score || 0) >= 60
    && daysUntil(j.deadline) >= 0
    && daysUntil(j.deadline) <= 7
  );
  if (urgentJob) {
    const days = daysUntil(urgentJob.deadline);
    const delay = days <= 0 ? "se termine aujourd'hui" : `se termine dans ${days} jour${plural(days, "", "s")}`;
    plan.push({
      title: `Postuler à « ${urgentJob.title} »`,
      note: `Chez ${urgentJob.company} · correspondance ${urgentJob.match_score}/100 · l'offre ${delay} (le ${fmtDeadline(urgentJob.deadline)}).`,
      to: `/opportunites/${urgentJob.id}`,
      cta: "Préparer ma candidature",
    });
  }
  // 2) Formation réelle pour le principal écart, avec la demande chiffrée.
  if (data.skills_to_improve[0]) {
    const skill = data.skills_to_improve[0];
    const gap = gapBySkill[skill];
    const demand = demandOf(skill);
    const reason = gap?.reason
      || (data.learning_focus
        ? `Ressource réelle : ${data.learning_focus.title} · ${data.learning_focus.provider}`
        : "Pour combler votre principal écart face aux offres.");
    plan.push({
      title: `Suivre une formation en ${skill}`,
      note: reason
        + (demand ? ` Demandée par ${demand} des ${activeOffers} offres actives.` : ""),
      to: data.learning_focus?.href
        ? mapInternalPath(data.learning_focus.href)
        : "/learning",
      cta: "Voir la formation",
    });
  }
  // 3) Renforcer la deuxième compétence, avec sa vraie demande.
  if (data.skills_to_improve[1]) {
    const skill = data.skills_to_improve[1];
    const gap = gapBySkill[skill];
    const demand = demandOf(skill);
    plan.push({
      title: `Renforcer ${skill}`,
      note: (gap?.reason || "Compétence émergente dans les offres de votre domaine.")
        + (demand ? ` Demandée par ${demand} des ${activeOffers} offres actives.` : ""),
      to: "/learning",
      cta: "Voir les formations",
    });
  }
  // 4) Adapter le CV pour la meilleure offre non encore postulée
  //    (remplace le conseil générique « Mettre à jour votre CV »).
  const topTarget = (data.top_matches || []).find((m) => !appliedIds.has(m.id));
  if (topTarget) {
    plan.push({
      title: `Adapter votre CV pour « ${topTarget.title} »`,
      note: `Chez ${topTarget.company} · correspondance ${topTarget.score}/100 : un CV ciblé sur l'offre pèse plus qu'un CV généraliste.`,
      to: `/opportunites/${topTarget.id}?galerie=cv`,
      cta: "Créer le CV ciblé",
    });
  } else if (comp && comp.missing?.length) {
    plan.push({
      title: `Compléter votre profil : ${comp.missing[0].toLowerCase()}`,
      note: "Les recruteurs filtrent sur ces informations : un profil complet remonte mieux.",
      to: "/profil",
      cta: "Compléter le profil",
    });
  }
  // 5) Cadrer le volume : combien d'offres correspondent vraiment.
  if (jobs.length > 0) {
    plan.push({
      title: jobs.length === 1
        ? "Passer en revue l'offre qui vous correspond"
        : `Passer en revue ${jobs.length} offres qui vous correspondent (45/100 et plus)`,
      note: topTarget
        ? `La meilleure du moment : « ${topTarget.title} » chez ${topTarget.company} (${topTarget.score}/100).`
        : "Le classement part des correspondances les plus fortes.",
      to: "/opportunites",
      cta: "Voir les offres",
    });
  }

  return (
    <div className="page">
      {/* ---------- Bandeau : message d'accueil de l'agent ---------- */}
      <section className="home-hero">
        <h1>Bonjour {firstName} {data.verified && <VerifiedBadge size={20} />}</h1>
        <p className="hero-agent-label">
          <Icon d={I.bot} size={14} /> {data.ai_label || "Le point de votre agent"}
        </p>
        <p className="hero-agent-briefing">{data.ai_briefing}</p>
        <Link className="btn btn-outline btn-small hero-agent-cta" to="/assistant">
          Discuter avec l'agent <ArrowIcon direction="right" size={11} />
        </Link>
      </section>

      {data.autonomous_prepared && (
        <div className="alert alert-success autonomous-flash">
          <Icon d={I.bot} size={16} />
          <div>
            <strong>Mode autonome :</strong> {data.autonomous_prepared.message}
            <Link
              className="btn btn-outline btn-small"
              to={`/opportunites/${data.autonomous_prepared.job_id}`}
            >
              Relire le CV et soumettre <ArrowIcon direction="right" size={11} />
            </Link>
          </div>
        </div>
      )}

      <div className="dash-columns">
        <div className="dash-col-main">
          {/* ---------- Prochaine meilleure action ---------- */}
          <section className="naa">
            <div className="naa-head">
              <Icon d={I.target} size={16} />
              <h2>Votre prochaine meilleure action</h2>
            </div>
            {bestJob ? (
              <>
                <h3 className="naa-title">{bestJob.title}</h3>
                <div className="chip-row" style={{ marginTop: 0 }}>
                  {bestJob.sector && <span className="chip">{bestJob.sector}</span>}
                  {bestJob.location && (
                    <span className="chip"><Icon d={I.pin} size={12} /> {bestJob.location}</span>
                  )}
                </div>
                <div className="naa-body">
                  {bestMatch && (
                    <div className="naa-ring">
                      <Ring score={bestMatch.score} text={`${bestMatch.score}/100`} />
                      <span className="naa-ring-label">Adéquation actuelle</span>
                    </div>
                  )}
                  {bestMatch && (
                    <div className="naa-side">
                      <p>
                        Vous avez déjà <strong>{bestMatch.covered.length} compétence{plural(bestMatch.covered.length, "", "s")} sur {coverageTotal}</strong>
                      </p>
                      <p className="small muted" style={{ marginTop: "0.35rem" }}>
                        {bestMatch.missing.length > 0
                          ? `Il vous manque ${bestMatch.missing.length} compétence${plural(bestMatch.missing.length, "", "s")} clé${plural(bestMatch.missing.length, "", "s")} pour atteindre un bon niveau.`
                          : "Toutes les compétences clés sont couvertes : vous êtes prêt à candidater."}
                      </p>
                    </div>
                  )}
                </div>
                {data.skills_to_improve.length > 0 && (
                  <div className="naa-priorities">
                    <span className="small muted">Vos priorités pour progresser</span>
                    <div className="naa-chips">
                      {data.skills_to_improve.slice(0, 3).map((s) => (
                        <span
                          key={s}
                          className="chip-soft"
                          title={gapBySkill[s]?.reason || ""}
                        >
                          <Icon d={I.zap} size={13} /> {s}
                        </span>
                      ))}
                    </div>
                    {gapDetails[0] && (
                      <p className="small muted" style={{ margin: "0.45rem 0 0" }}>
                        {gapDetails[0].reason}
                      </p>
                    )}
                  </div>
                )}
                <div className="naa-actions">
                  <Link className="btn btn-primary" to="/profil">
                    Améliorer mon profil <ArrowIcon direction="right" size={13} />
                  </Link>
                  <Link className="btn btn-outline" to={`/opportunites/${bestJob.id}`}>
                    Voir l'offre complète
                  </Link>
                </div>
              </>
            ) : (
              <>
                <h3 className="naa-title">{na?.label}</h3>
                <div className="naa-actions">
                  <Link className="btn btn-primary" to={naTo}>
                    Passer à l'action <ArrowIcon direction="right" size={13} />
                  </Link>
                </div>
              </>
            )}
          </section>

          {/* ---------- Opportunités ---------- */}
          <section className="dash-card">
            <div className="dash-card-head">
              <h2>
                {jobs.length} opportunité{plural(jobs.length, "", "s")} qui correspondent à votre profil
              </h2>
              <Link className="link-more" to="/opportunites">
                Voir toutes les opportunités <ArrowIcon direction="right" />
              </Link>
            </div>
            <p className="small muted" style={{ marginTop: 0 }}>
              Classées par correspondance décroissante avec votre profil validé.
            </p>
            {jobs.length > 0 ? (
              <div className="opp-cards">
                {jobs.slice(0, 3).map((j) => (
                  <Link key={j.id} className="opp-card" to={`/opportunites/${j.id}`}>
                    <div className="opp-card-media">
                      <span>{initialsOf(j.company)}</span>
                      {j.match_score != null && (
                        <span className="opp-card-score">{j.match_score}/100</span>
                      )}
                    </div>
                    <div className="opp-card-body">
                      <span className="opp-card-title">{j.title}</span>
                      <span className="opp-card-meta"><Icon d={I.briefcase} size={13} /> {j.company}</span>
                      <span className="opp-card-meta"><Icon d={I.pin} size={13} /> {j.location}</span>
                      <span className="opp-card-meta">
                        {j.contract_type}{j.sector ? ` · ${j.sector}` : ""}
                      </span>
                      <span className="btn btn-primary btn-small">
                        Voir l'offre <ArrowIcon direction="right" size={12} />
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="muted small">
                Aucune correspondance pour l'instant. Complétez votre profil pour affiner le matching.
              </p>
            )}
          </section>

          {/* ---------- Votre progression ---------- */}
          {comp && (
            <section className="dash-card">
              <div className="dash-card-head">
                <h2>Votre progression</h2>
                <Link className="link-more" to="/profil">
                  Voir mon profil <ArrowIcon direction="right" />
                </Link>
              </div>
              <p className="small muted" style={{ marginTop: 0 }}>
                {comp.score >= 75
                  ? "Vous êtes sur la bonne voie : continuez sur cette lancée."
                  : "Encore un effort : chaque élément complété renforce votre score."}
              </p>
              <div className="progress-head">
                <div className="progress-global">
                  <Ring score={comp.score} text={`${comp.score}%`} />
                  <span className="naa-ring-label">Score de votre profil</span>
                </div>
                <div className="score-bars">
                  <div className="score-bar-row">
                    <div className="score-bar-top">
                      <span>Profil complété</span>
                      <b>{comp.score}/100</b>
                    </div>
                    <span className="score-bar-track">
                      <span className="score-bar-fill fill-green" style={{ width: `${comp.score}%` }} />
                    </span>
                  </div>
                  {bestScore != null && (
                    <div className="score-bar-row">
                      <div className="score-bar-top">
                        <span>Meilleure correspondance</span>
                        <b>{bestScore}/100</b>
                      </div>
                      <span className="score-bar-track">
                        <span className="score-bar-fill fill-blue" style={{ width: `${bestScore}%` }} />
                      </span>
                    </div>
                  )}
                  {avgScore != null && (
                    <div className="score-bar-row">
                      <div className="score-bar-top">
                        <span>Adéquation moyenne sur {scored.length} offre{plural(scored.length, "", "s")}</span>
                        <b>{avgScore}/100</b>
                      </div>
                      <span className="score-bar-track">
                        <span className="score-bar-fill fill-violet" style={{ width: `${avgScore}%` }} />
                      </span>
                    </div>
                  )}
                </div>
                <div className="next-step-panel">
                  <h3>Prochaine étape</h3>
                  <p>
                    {data.skills_to_improve.length > 0
                      ? `Renforcez ${data.skills_to_improve.length} compétence${plural(data.skills_to_improve.length, "", "s")} demandée${plural(data.skills_to_improve.length, "", "s")} par le marché pour élargir vos opportunités.`
                      : "Tenez votre profil à jour pour rester visible auprès des recruteurs."}
                  </p>
                  <Link
                    className="btn btn-primary btn-small"
                    to={data.learning_focus?.href
                      ? mapInternalPath(data.learning_focus.href)
                      : "/learning"}
                  >
                    Voir mon plan d'amélioration <ArrowIcon direction="right" size={12} />
                  </Link>
                </div>
              </div>
            </section>
          )}

          {/* ---------- Plan de la semaine ---------- */}
          <section className="dash-card">
            <div className="dash-card-head">
              <h2>Votre plan cette semaine</h2>
            </div>
            <p className="small muted" style={{ marginTop: 0 }}>
              Calculé à partir de {activeOffers} offre{plural(activeOffers, "", "s")} active{plural(activeOffers, "", "s")} et de votre profil validé.
            </p>
            <div className="plan-grid">
              {plan.map((a, i) => (
                <div key={a.title} className="plan-card">
                  <span className="plan-num">{i + 1}</span>
                  <span className="plan-title">{a.title}</span>
                  <span className="plan-note">{a.note}</span>
                  <Link className={`btn btn-small ${i === 0 ? "btn-primary" : "btn-outline"}`} to={a.to}>
                    {a.cta} <ArrowIcon direction="right" size={12} />
                  </Link>
                </div>
              ))}
            </div>
          </section>

          {/* ---------- Compétences qui montent ---------- */}
          {rising.length > 0 && (
            <section className="dash-card">
              <div className="dash-card-head">
                <h2>Compétences qui montent</h2>
                <Link className="link-more" to="/carriere">
                  Voir toutes les tendances <ArrowIcon direction="right" />
                </Link>
              </div>
              <p className="small muted" style={{ marginTop: 0 }}>
                Part des offres qui demandent ces compétences, comparée aux 7 jours précédents.
              </p>
              <div className="chip-row">
                {rising.map((t) => (
                  <span key={t.name} className="trend-chip">
                    {t.name}
                    <b>+{t.pct_change} %</b>
                  </span>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* ---------- Colonne latérale ---------- */}
        <div className="dash-col-side">
          <section className="dash-card">
            <div className="dash-card-head">
              <h2>Mon parcours</h2>
            </div>
            <p className="small muted" style={{ marginTop: 0 }}>
              Avancez étape par étape vers votre objectif.
            </p>

            <Link className="journey-row" to="/profil">
              <span className="journey-icon green"><Icon d={I.user} size={16} /></span>
              <span className="journey-main">
                <span className="journey-top">
                  <span>Profil</span>
                  <span>{comp ? `${comp.score} %` : "Aucun"}</span>
                </span>
                <span className="journey-sub">Complétude de votre profil</span>
              </span>
              <Icon d={I.arrow} size={15} />
            </Link>

            <Link className="journey-row" to="/competences">
              <span className="journey-icon blue"><Icon d={I.zap} size={16} /></span>
              <span className="journey-main">
                <span className="journey-top">
                  <span>Compétences</span>
                  <span>{profile.skills?.length || 0}</span>
                </span>
                <span className="journey-sub">Compétences déclarées</span>
              </span>
              <Icon d={I.arrow} size={15} />
            </Link>

            <Link className="journey-row" to="/opportunites">
              <span className="journey-icon violet"><Icon d={I.target} size={16} /></span>
              <span className="journey-main">
                <span className="journey-top">
                  <span>Opportunités</span>
                  <span>{data.strong_matches}</span>
                </span>
                <span className="journey-sub">Correspondances fortes</span>
              </span>
              <Icon d={I.arrow} size={15} />
            </Link>

            <Link className="journey-row" to="/candidatures">
              <span className="journey-icon slate"><Icon d={I.clipboard} size={16} /></span>
              <span className="journey-main">
                <span className="journey-top">
                  <span>Candidatures</span>
                  <span>{data.ongoing_applications}</span>
                </span>
                <span className="journey-sub">En cours</span>
              </span>
              <Icon d={I.arrow} size={15} />
            </Link>
          </section>

          <section className="assistant-cta">
            <span className="agent-mascot"><Icon d={I.bot} size={22} /></span>
            <div>
              <h3>L'IA travaille pour vous</h3>
              <p>Des recommandations personnalisées, selon votre profil et le marché de l'emploi.</p>
              <Link className="btn btn-primary btn-small" to="/agent">
                Parler à l'assistant <ArrowIcon direction="right" size={12} />
              </Link>
            </div>
          </section>

          {data.market_trends.length > 0 && (
            <section className="dash-card">
              <div className="dash-card-head">
                <h2><Icon d={I.sun} size={15} /> Le point du jour</h2>
              </div>
              <p className="small muted" style={{ marginTop: 0 }}>
                Les tendances de la semaine sur votre marché.
              </p>
              <ul className="point-list">
                {data.market_trends.slice(0, 4).map((t) => (
                  <li key={t.name}>
                    <span>
                      {t.name}
                      <br />
                      <span className="count">{t.offers} offre{plural(t.offers, "", "s")} cette semaine</span>
                    </span>
                    <span className={t.trend === "down" ? "down" : "up"}>
                      {t.pct_change > 0 ? `+${t.pct_change}` : t.pct_change} %
                    </span>
                  </li>
                ))}
              </ul>
              <Link className="link-more" to="/carriere">
                Voir toutes les tendances <ArrowIcon direction="right" />
              </Link>
            </section>
          )}

          <section className="quote-card">
            <Icon d={I.spark} size={18} />
            <p>« Votre parcours n'est pas une ligne droite, c'est une série de bonnes décisions. »</p>
            <cite>OrientSkill AI</cite>
          </section>

          <section className="advice-card">
            <span className="journey-icon green"><Icon d={I.lightbulb} size={17} /></span>
            <div>
              <h3>Besoin d'un conseil ?</h3>
              <p>Parlez à notre assistante IA pour obtenir des recommandations personnalisées.</p>
              <Link className="btn btn-outline btn-small" to="/agent">
                Ouvrir l'assistant <ArrowIcon direction="right" size={12} />
              </Link>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
