import { fmtDate } from "../lib.js";

// Fiche publique d'une offre, partagée entre la page de candidature et
// l'aperçu du recruteur. Une seule source de vérité pour le rendu final :
// branding, photo, compétences, salaire et référence.
export default function JobPublicView({ job, preview = false, titleTag = "h1" }) {
  if (!job) return null;
  const Heading = titleTag;
  const company = job.company || job.company_branding?.name || "";
  const reference = job.email_reference || "";
  const skills = job.required_skills || [];

  return (
    <section className="public-job">
      <p className="public-job-company">
        {company}
        {company && job.location ? " · " : ""}
        {job.location}
      </p>
      <Heading className="public-job-title">
        {job.title || "Intitulé à compléter"}
      </Heading>
      <div className="public-job-tags">
        {job.contract_type && <span className="chip">{job.contract_type}</span>}
        {job.sector && <span className="chip">{job.sector}</span>}
        {job.salary && <span className="chip">{job.salary}</span>}
        {job.deadline && (
          <span className="chip">
            Candidature jusqu'au {fmtDate(job.deadline)}
          </span>
        )}
        {reference ? (
          <span className="chip">Réf. {reference}</span>
        ) : preview ? (
          <span className="chip">Réf. attribuée après publication</span>
        ) : null}
      </div>
      {job.photo_url && (
        <img className="public-job-photo" src={job.photo_url} alt="" />
      )}
      {job.description ? (
        <p className="public-job-desc">{job.description}</p>
      ) : preview ? (
        <p className="public-job-desc muted">Description à compléter.</p>
      ) : null}
      {job.requirements && (
        <>
          <h2>Profil recherché</h2>
          <p className="public-job-desc">{job.requirements}</p>
        </>
      )}
      {skills.length > 0 && (
        <>
          <h2>Compétences demandées</h2>
          <div className="chip-row">
            {skills.map((skill) => (
              <span className="chip" key={skill.name}>
                {skill.name}
                {skill.importance === "core" ? " · essentielle" : ""}
              </span>
            ))}
          </div>
        </>
      )}
      {job.company_branding?.description && (
        <>
          <h2>L'entreprise</h2>
          <p className="public-job-desc">{job.company_branding.description}</p>
        </>
      )}
      {job.source?.url && (
        <p className="small muted">
          Source : {job.source.name || "lien d'origine"} ·{" "}
          <a href={job.source.url} target="_blank" rel="noreferrer">
            consulter l'annonce d'origine
          </a>
        </p>
      )}
    </section>
  );
}
