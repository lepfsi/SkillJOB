import { useState } from "react";
import { apiRaw } from "../api/client.js";
import Avatar from "./Avatar.jsx";
import VerifiedBadge from "./VerifiedBadge.jsx";
import {
  EXPERIENCE_TYPE_LABELS,
  PROFICIENCY_LABELS,
  SOURCE_LABELS,
  fmtDate,
  plural,
} from "../lib.js";
import { Icon, I } from "./icons.jsx";
import { ErrorNote } from "./ui.jsx";

// Carte de profil complète côté recruteur. Elle reprend la direction
// visuelle du profil talent (bannière, faits, cartes) et n'affiche que
// les données validées du profil. Le CV n'apparaît que si le talent a
// activé son partage et choisi un CV généraliste.

const PROFICIENCY_METER = { debutant: 40, intermediaire: 70, avance: 92 };

function fmtMonth(value) {
  if (!value) return "";
  const [year, month] = String(value).split("-");
  if (!year) return String(value);
  if (!month) return year;
  const date = new Date(Number(year), Number(month) - 1, 1);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("fr-FR", { month: "short", year: "numeric" });
}

function fmtPeriod(start, end) {
  const first = fmtMonth(start);
  const last = end ? fmtMonth(end) : "aujourd'hui";
  return [first, last].filter(Boolean).join(" à ");
}

function fmtYears(start, end) {
  if (!start && !end) return "";
  return [start, end || "aujourd'hui"].filter(Boolean).join(" à ");
}

function ProfileBox({ icon, title, children, className = "" }) {
  return (
    <section className={`dash-card ${className}`.trim()}>
      <div className="dash-card-head">
        <h2>{icon && <Icon d={icon} size={16} />} {title}</h2>
      </div>
      {children}
    </section>
  );
}

function SkillLine({ skill }) {
  const pct = PROFICIENCY_METER[skill.proficiency] || 40;
  return (
    <div className="pf-skill">
      <div className="pf-skill-line">
        <span className="pf-skill-name">{skill.skill}</span>
        <span className="pf-skill-level">
          {PROFICIENCY_LABELS[skill.proficiency] || "Non renseigné"}
        </span>
      </div>
      <div className="pf-skill-bar">
        <span className="pf-skill-fill" style={{ width: `${pct}%` }} />
      </div>
      {skill.source && (
        <span className="pf-skill-note">{SOURCE_LABELS[skill.source] || ""}</span>
      )}
    </div>
  );
}

export default function TalentProfile({
  candidate,
  onContact,
  onAddToShortlist,
}) {
  const [cvBusy, setCvBusy] = useState(false);
  const [cvError, setCvError] = useState("");

  const skills = candidate.skills || [];
  const skillDetails = candidate.skill_details || [];
  const experiences = candidate.experiences || [];
  const education = candidate.education || [];
  const certifications = candidate.certifications || [];
  const languages = candidate.languages || [];
  const projects = candidate.projects || [];
  const preferences = candidate.preferences || {};
  const sharedCv = candidate.cv || null;

  async function downloadCv() {
    if (!sharedCv) return;
    setCvBusy(true);
    setCvError("");
    try {
      const res = await apiRaw(`/recruiter/candidates/${candidate.user_id}/cv`);
      if (!res.ok) throw new Error("Le CV n'est pas accessible.");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `CV-${candidate.full_name || candidate.user_id}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setCvError(err.message || "Téléchargement impossible.");
    } finally {
      setCvBusy(false);
    }
  }

  return (
    <div className="talent-profile">
      <section className="pf-hero talent-profile-hero">
        <div className="pf-cover" aria-hidden="true">
          <span className="pf-cover-glow" />
        </div>
        <div className="talent-profile-hero-grid">
          <Avatar
            name={candidate.full_name}
            photoUrl={candidate.photo_url}
            className="pf-avatar talent-profile-avatar"
          />

          <div className="pf-id">
            <div className="pf-name-row">
              <h1>{candidate.full_name}</h1>
              {candidate.verified && <VerifiedBadge size={20} />}
            </div>
            <p className="pf-title">
              {candidate.title || "Titre professionnel non renseigné"}
            </p>
            <div className="pf-meta">
              {candidate.location && (
                <span><Icon d={I.pin} size={14} /> {candidate.location}</span>
              )}
              {candidate.availability && (
                <span className="pf-avail"><span className="pf-dot" /> {candidate.availability}</span>
              )}
              {candidate.mobility && (
                <span><Icon d={I.compass} size={14} /> Mobilité : {candidate.mobility}</span>
              )}
            </div>
            {skills.length > 0 && (
              <div className="pf-chips">
                {skills.slice(0, 5).map((skill) => (
                  <span key={skill} className="chip chip-soft">{skill}</span>
                ))}
              </div>
            )}
          </div>

          <aside className="talent-profile-actions">
            <span className="talent-profile-privacy">
              <Icon d={I.shield} size={14} />
              {sharedCv ? "CV partagé par le talent" : "Coordonnées protégées"}
            </span>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => onContact?.(candidate)}
            >
              <Icon d={I.mail} size={14} /> Contacter
            </button>
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => onAddToShortlist?.(candidate)}
            >
              <Icon d={I.folder} size={14} /> Ajouter à une shortlist
            </button>
          </aside>
        </div>
      </section>

      <div className="talent-profile-facts">
        <div>
          <strong>{experiences.length}</strong>
          <span>expérience{plural(experiences.length, "", "s")}</span>
        </div>
        <div>
          <strong>{education.length}</strong>
          <span>formation{plural(education.length, "", "s")}</span>
        </div>
        <div>
          <strong>{certifications.length}</strong>
          <span>certification{plural(certifications.length, "", "s")}</span>
        </div>
        <div>
          <strong>{skills.length}</strong>
          <span>compétence{plural(skills.length, "", "s")}</span>
        </div>
      </div>

      {candidate.summary && (
        <section className="pf-insight">
          <span className="pf-insight-icon"><Icon d={I.spark} size={20} /></span>
          <div className="pf-insight-body">
            <h2>Le profil en un coup d'œil</h2>
            <p className="pf-insight-sub">
              Résumé rédigé à partir du profil validé par le talent.
            </p>
            <p className="pf-insight-text">{candidate.summary}</p>
          </div>
        </section>
      )}

      <div className="talent-profile-grid">
        <div className="talent-profile-main">
          <ProfileBox icon={I.briefcase} title="Expériences">
            {experiences.length === 0 ? (
              <p className="muted small">Aucune expérience renseignée.</p>
            ) : (
              <ul className="pf-timeline">
                {experiences.map((item) => (
                  <li key={item.id || `${item.title}-${item.start_date}`}>
                    <span className="pf-timeline-dot">
                      <Icon d={I.briefcase} size={14} />
                    </span>
                    <div className="pf-timeline-body">
                      <div className="pf-timeline-head">
                        <strong>{item.title}</strong>
                        <span className="chip chip-soft">
                          {EXPERIENCE_TYPE_LABELS[item.type] || "Expérience"}
                        </span>
                      </div>
                      <span className="opp-meta">
                        {[item.organization, fmtPeriod(item.start_date, item.end_date)]
                          .filter(Boolean).join(" · ")}
                      </span>
                      {item.description && (
                        <p className="pf-timeline-text">{item.description}</p>
                      )}
                      {item.skills?.length > 0 && (
                        <div className="pf-chips pf-chips-tight">
                          {item.skills.map((skill) => (
                            <span key={skill} className="chip chip-mini">{skill}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </ProfileBox>

          <ProfileBox icon={I.cap} title="Formation">
            {education.length === 0 ? (
              <p className="muted small">Aucune formation renseignée.</p>
            ) : (
              <ul className="pf-list">
                {education.map((item) => (
                  <li key={item.id || item.degree}>
                    <strong>{item.degree}</strong>
                    <span className="opp-meta">
                      {[item.institution, fmtYears(item.start_year, item.end_year)]
                        .filter(Boolean).join(" · ")}
                    </span>
                    {item.field && <span className="pf-timeline-text">{item.field}</span>}
                  </li>
                ))}
              </ul>
            )}
          </ProfileBox>

          <ProfileBox icon={I.award} title="Certifications">
            {certifications.length === 0 ? (
              <p className="muted small">Aucune certification renseignée.</p>
            ) : (
              <div className="talent-cert-grid">
                {certifications.map((item) => (
                  <article className="talent-cert" key={item.id || item.name}>
                    <span className="talent-cert-icon"><Icon d={I.award} size={17} /></span>
                    <div>
                      <strong>{item.name}</strong>
                      <span className="opp-meta">
                        {[item.issuer, item.year].filter(Boolean).join(" · ")}
                      </span>
                      {item.skills?.length > 0 && (
                        <div className="pf-chips pf-chips-tight">
                          {item.skills.map((skill) => (
                            <span key={skill} className="chip chip-mini">{skill}</span>
                          ))}
                        </div>
                      )}
                      {item.url && (
                        <a className="link-more" href={item.url} target="_blank" rel="noreferrer">
                          Vérifier la certification
                        </a>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </ProfileBox>

          <ProfileBox icon={I.folder} title="Projets et réalisations">
            {projects.length === 0 ? (
              <p className="muted small">Aucun projet renseigné.</p>
            ) : (
              <div className="pf-projects">
                {projects.map((project) => (
                  <article className="pf-project" key={project.id || project.name}>
                    <span className="pf-project-icon"><Icon d={I.folder} size={18} /></span>
                    <div>
                      <strong>{project.name}</strong>
                      {project.skills?.length > 0 && (
                        <div className="pf-chips pf-chips-tight">
                          {project.skills.map((skill) => (
                            <span key={skill} className="chip chip-mini">{skill}</span>
                          ))}
                        </div>
                      )}
                      {project.description && (
                        <p className="pf-timeline-text">{project.description}</p>
                      )}
                      {project.url && (
                        <a className="link-more" href={project.url} target="_blank" rel="noreferrer">
                          Voir la réalisation
                        </a>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </ProfileBox>
        </div>

        <aside className="talent-profile-side">
          <ProfileBox icon={I.zap} title="Compétences">
            {skills.length === 0 ? (
              <p className="muted small">Aucune compétence renseignée.</p>
            ) : (
              <div className="pf-skills">
                {skillDetails.length > 0
                  ? skillDetails.map((skill) => (
                    <SkillLine key={skill.skill} skill={skill} />
                  ))
                  : skills.map((skill) => (
                    <span className="chip chip-soft" key={skill}>{skill}</span>
                  ))}
              </div>
            )}
          </ProfileBox>

          <ProfileBox icon={I.globe} title="Langues">
            {languages.length === 0 ? (
              <p className="muted small">Aucune langue renseignée.</p>
            ) : (
              <dl className="pf-prefs">
                {languages.map((language) => (
                  <div key={language.id || language.language}>
                    <dt>{language.language}</dt>
                    <dd>{language.level || "Non renseigné"}</dd>
                  </div>
                ))}
              </dl>
            )}
          </ProfileBox>

          <ProfileBox icon={I.settings} title="Préférences">
            <dl className="pf-prefs">
              <div>
                <dt><Icon d={I.clipboard} size={14} /> Contrats</dt>
                <dd>
                  {preferences.contract_types?.length
                    ? preferences.contract_types.join(" / ")
                    : "Non renseigné"}
                </dd>
              </div>
              <div>
                <dt><Icon d={I.compass} size={14} /> Mobilité</dt>
                <dd>{candidate.mobility || "Non renseignée"}</dd>
              </div>
              <div>
                <dt><Icon d={I.globe} size={14} /> Télétravail</dt>
                <dd>{preferences.remote_ok ? "Accepté" : "Non accepté"}</dd>
              </div>
              <div>
                <dt><Icon d={I.target} size={14} /> Secteurs</dt>
                <dd>
                  {preferences.sectors?.length
                    ? preferences.sectors.join(", ")
                    : "Non renseignés"}
                </dd>
              </div>
            </dl>
          </ProfileBox>

          {sharedCv ? (
            <section className="talent-cv is-shared">
              <span className="talent-cv-icon"><Icon d={I.file} size={20} /></span>
              <div className="talent-cv-copy">
                <span className="talent-cv-eyebrow">Partagé par le talent</span>
                <h2>CV généraliste</h2>
                <p>{sharedCv.title}</p>
                <p className="small muted">
                  Mis à jour le {fmtDate(sharedCv.created_at)}
                </p>
              </div>
              <button
                type="button"
                className="btn btn-primary btn-small"
                onClick={downloadCv}
                disabled={cvBusy}
              >
                <Icon d={I.file} size={12} />
                {cvBusy ? "Téléchargement…" : "Télécharger le CV PDF"}
              </button>
              <ErrorNote error={cvError} />
            </section>
          ) : (
            <section className="talent-cv is-private">
              <span className="talent-cv-icon"><Icon d={I.shield} size={20} /></span>
              <div className="talent-cv-copy">
                <span className="talent-cv-eyebrow">Confidentialité</span>
                <h2>CV non partagé</h2>
                <p>
                  Ce talent n'a pas activé le partage de son CV généraliste.
                  Le contact reste possible par la messagerie interne.
                </p>
              </div>
            </section>
          )}

          {candidate.updated_at && (
            <p className="small muted talent-profile-updated">
              Profil mis à jour le {fmtDate(candidate.updated_at)}.
            </p>
          )}
        </aside>
      </div>
    </div>
  );
}
