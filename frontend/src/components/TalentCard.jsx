import { Link } from "react-router-dom";
import Avatar from "./Avatar.jsx";
import MatchBadge from "./MatchBadge.jsx";
import SkillTag from "./SkillTag.jsx";
import { ArrowIcon, Icon, I } from "./icons.jsx";
import { plural } from "../lib.js";

// Carte talent partagée entre le tableau de bord recruteur, la recherche
// et la fiche détaillée. Elle n'affiche que les faits du profil : aucune
// disponibilité, expérience ou coordonnée inventée (§47).

export default function TalentCard({
  candidate,
  onContact,
  onAddToShortlist,
  profileHref,
  full = false,
}) {
  const skills = candidate.skills || [];
  const topCertifications = candidate.top_certifications || [];
  const match = candidate.match && candidate.match.score > 0
    ? candidate.match
    : null;
  const visibleSkills = skills.slice(0, full ? 24 : 8);
  const hiddenSkills = skills.length - visibleSkills.length;

  return (
    <article className={`talent-card${full ? " is-full" : ""}`}>
      <div className="talent-card-header">
        <Avatar
          name={candidate.full_name}
          photoUrl={candidate.photo_url}
          className="talent-avatar"
        />
        <div className="talent-card-id">
          <div className="talent-card-titleline">
            <h2>{candidate.full_name}</h2>
            {candidate.verified ? (
              <span className="verified-chip">
                <Icon d={I.shield} size={11} />
                Profil vérifié
              </span>
            ) : (
              <span className="badge badge-none">Non vérifié</span>
            )}
          </div>
          <p className="talent-role">
            {candidate.title || "Profil en construction"}
          </p>
          <div className="talent-meta">
            {candidate.location && (
              <span className="talent-meta-item">
                <Icon d={I.pin} size={12} />
                {candidate.location}
              </span>
            )}
            {skills.length > 0 && (
              <span className="talent-meta-item">
                <Icon d={I.layers} size={12} />
                {skills.length} compétence{plural(skills.length, "", "s")}
              </span>
            )}
            {(candidate.experience_count || 0) > 0 && (
              <span className="talent-meta-item">
                <Icon d={I.briefcase} size={12} />
                {candidate.experience_count} expérience{plural(candidate.experience_count, "", "s")}
              </span>
            )}
            {(candidate.certification_count || 0) > 0 && (
              <span className="talent-meta-item">
                <Icon d={I.award} size={12} />
                {candidate.certification_count} certification{plural(candidate.certification_count, "", "s")}
              </span>
            )}
            {candidate.cv && (
              <span className="talent-meta-item talent-cv-pill">
                <Icon d={I.file} size={12} />
                CV partagé
              </span>
            )}
          </div>
        </div>
      </div>

      {candidate.summary && (
        <p className="talent-summary">{candidate.summary}</p>
      )}

      {topCertifications.length > 0 && (
        <div className="talent-cert-strip">
          <span className="talent-cert-strip-label">Certifications</span>
          <div className="chip-row">
            {topCertifications.map((name) => (
              <span key={name} className="chip chip-soft talent-cert-chip">
                <Icon d={I.award} size={11} /> {name}
              </span>
            ))}
          </div>
        </div>
      )}

      {match && (
        <div className="talent-match">
          <div className="talent-match-head">
            <span className="talent-match-label">
              Correspondance avec votre recherche
            </span>
            <MatchBadge score={match.score} />
          </div>
          <div className="chip-row">
            {match.covered.map((skill) => (
              <SkillTag key={skill} name={skill} state="covered" />
            ))}
            {match.partial.map((skill) => (
              <SkillTag key={skill} name={skill} state="partial" />
            ))}
            {match.missing.map((skill) => (
              <SkillTag key={skill} name={skill} state="missing" />
            ))}
          </div>
        </div>
      )}

      {skills.length > 0 && (
        <div className="talent-skills-block">
          {full && <span className="talent-skills-label">Compétences</span>}
          <div className="talent-skills">
            {visibleSkills.map((skill) => (
              <span className="chip talent-skill" key={skill}>{skill}</span>
            ))}
            {hiddenSkills > 0 && (
              <span className="talent-skills-more">
                +{hiddenSkills} autre{plural(hiddenSkills, "", "s")}
              </span>
            )}
          </div>
        </div>
      )}

      {(profileHref || onAddToShortlist || onContact) && (
        <div className="talent-actions">
          {profileHref && (
            <Link className="talent-profile-link" to={profileHref}>
              Voir la carte de profil
              <ArrowIcon direction="right" size={11} />
            </Link>
          )}
          <div className="talent-actions-buttons">
            {onAddToShortlist && (
              <button
                type="button"
                className="btn btn-outline btn-small"
                onClick={() => onAddToShortlist(candidate)}
              >
                Ajouter à une shortlist
              </button>
            )}
            {onContact && (
              <button
                type="button"
                className="btn btn-primary btn-small"
                onClick={() => onContact(candidate)}
              >
                Contacter
              </button>
            )}
          </div>
        </div>
      )}
    </article>
  );
}
