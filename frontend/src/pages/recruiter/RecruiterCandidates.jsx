import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../../api/client.js";
import SkillTag from "../../components/SkillTag.jsx";
import MatchBadge from "../../components/MatchBadge.jsx";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";

// Talent search (§21) : recherche par compétences avec matching
// explicable, et carte de profil — TOUT ce que voit le recruteur.

function CandidateCard({ candidate, onContact, onAddToShortlist, full = false }) {
  const initials = candidate.full_name
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <div className="talent-card">
      <div className="talent-card-header">
        <div className="talent-avatar">{initials}</div>
        <div className="talent-card-id">
          <h2 style={{ margin: 0 }}>{candidate.full_name}</h2>
          <p className="job-meta" style={{ margin: "0.15rem 0" }}>
            {candidate.title || "Profil en construction"}
            {candidate.location ? ` · ${candidate.location}` : ""}
          </p>
        </div>
        {candidate.verified ? (
          <span className="verified-chip">Profil vérifié</span>
        ) : (
          <span className="badge badge-none">Non vérifié</span>
        )}
      </div>

      {full && candidate.summary && <p className="talent-summary">{candidate.summary}</p>}

      {candidate.match && candidate.match.score > 0 && (
        <div className="talent-match">
          <MatchBadge score={candidate.match.score} />
          <div className="chip-row" style={{ marginTop: "0.4rem" }}>
            {candidate.match.covered.map((s) => (
              <SkillTag key={s} name={s} state="covered" />
            ))}
            {candidate.match.partial.map((s) => (
              <SkillTag key={s} name={s} state="partial" />
            ))}
            {candidate.match.missing.map((s) => (
              <SkillTag key={s} name={s} state="missing" />
            ))}
          </div>
        </div>
      )}

      {candidate.skills && candidate.skills.length > 0 && (
        <div className="talent-skills">
          {candidate.skills.slice(0, 8).map((s) => (
            <span className="chip" key={s}>{s}</span>
          ))}
          {candidate.skills.length > 8 && (
            <span className="small muted">+{candidate.skills.length - 8} autre(s)</span>
          )}
        </div>
      )}

      {(onContact || onAddToShortlist) && (
        <div className="talent-actions">
          {onAddToShortlist && (
            <button className="btn btn-outline btn-small" onClick={() => onAddToShortlist(candidate.user_id)}>
              Ajouter à une shortlist
            </button>
          )}
          {onContact && (
            <button className="btn btn-primary btn-small" onClick={() => onContact(candidate.user_id)}>
              Contacter
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function RecruiterCandidates() {
  const [candidates, setCandidates] = useState(null);
  const [skills, setSkills] = useState("");
  const [q, setQ] = useState("");
  const [region, setRegion] = useState("");
  const [sector, setSector] = useState("");
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [geoRegions, setGeoRegions] = useState([]);
  const [shortlists, setShortlists] = useState([]);
  const [error, setError] = useState("");
  const { candidateId } = useParams();
  const navigate = useNavigate();

  const isDetail = !!candidateId;

  useEffect(() => {
    if (isDetail) return;
    const params = new URLSearchParams();
    if (skills.trim()) params.set("skills", skills.trim());
    if (q.trim()) params.set("q", q.trim());
    if (region) params.set("region", region);
    if (sector.trim()) params.set("sector", sector.trim());
    if (verifiedOnly) params.set("verified_only", "true");
    const timer = setTimeout(() => {
      api(`/recruiter/candidates?${params.toString()}`)
        .then(setCandidates)
        .catch((e) => setError(e.detail));
    }, 250);
    return () => clearTimeout(timer);
  }, [skills, q, region, sector, verifiedOnly, isDetail]);

  const [card, setCard] = useState(null);
  const [cardError, setCardError] = useState("");

  useEffect(() => {
    api("/geo").then((d) => setGeoRegions(d.regions || [])).catch(() => {});
    api("/recruiter/shortlists").then(setShortlists).catch(() => setShortlists([]));
  }, []);

  async function addToShortlist(candidateId) {
    if (shortlists.length === 0) {
      const name = window.prompt(
        "Vous n'avez pas encore de shortlist. Nom de la première liste :",
        "Ma première shortlist"
      );
      if (!name) return;
      await api("/recruiter/shortlists", { method: "POST", body: { name } });
      await api("/recruiter/shortlists").then(setShortlists);
    }
    const names = shortlists.map((s) => `${s.id} · ${s.name}`).join("\n");
    const choice = window.prompt(
      `Ajouter à quelle shortlist ? (numéro)\n\n${names}`,
      shortlists[0]?.id
    );
    if (!choice) return;
    try {
      await api(`/recruiter/shortlists/${choice}/items`, {
        method: "POST",
        body: { candidate_id: candidateId },
      });
    } catch (err) {
      setError(err.detail);
    }
  }

  useEffect(() => {
    if (!isDetail) return;
    setCard(null);
    api(`/recruiter/candidates/${candidateId}`)
      .then(setCard)
      .catch((e) => setCardError(e.detail));
  }, [candidateId, isDetail]);

  async function contact(id) {
    const body = window.prompt(
      "Message au candidat :",
      "Bonjour, votre profil correspond à l'un de nos postes. Êtes-vous disponible pour un échange ?"
    );
    if (!body) return;
    try {
      await api("/messages", { method: "POST", body: { recipient_id: id, body } });
      navigate(`/messages/${id}`);
    } catch (err) {
      setError(err.detail);
    }
  }

  if (isDetail) {
    if (cardError) {
      return (
        <div className="page">
          <ErrorNote error={cardError} />
          <button className="btn btn-ghost" onClick={() => navigate("/recruteur/candidats")}>← Retour</button>
        </div>
      );
    }
    if (!card) {
      return <div className="page"><Loader /></div>;
    }
    return (
      <div className="page page-narrow">
        <button className="btn btn-ghost btn-small" onClick={() => navigate("/recruteur/candidats")}>
          ← Recherche
        </button>
        <CandidateCard candidate={card} onContact={contact} onAddToShortlist={addToShortlist} full />
        <p className="small muted">
          Le contact passe par la messagerie interne : les coordonnées du
          candidat ne sont jamais exposées dans la recherche.
        </p>
      </div>
    );
  }

  if (error && !candidates) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!candidates) {
    return <div className="page"><Loader /></div>;
  }

  return (
    <div className="page">
      <h1>Recherche de talents</h1>
      <p className="page-lead">
        Cherchez par compétences : le matching est expliqué (couvertes,
        partielles, manquantes), jamais un score opaque.
      </p>

      <div className="filters">
        <label className="field" style={{ gridColumn: "1 / -1" }}>
          <span>Compétences recherchées (séparées par des virgules)</span>
          <input
            value={skills}
            onChange={(e) => setSkills(e.target.value)}
            placeholder="Ex. TCP/IP, Fortinet, Linux"
          />
        </label>
        <label className="field">
          <span>Métier / titre recherché</span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Ex. technicien, comptable…"
          />
        </label>
        <label className="field">
          <span>Région</span>
          <select value={region} onChange={(e) => setRegion(e.target.value)}>
            <option value="">Toutes</option>
            {geoRegions.map((r) => <option key={r.name}>{r.name}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Secteur d'activité visé</span>
          <input
            value={sector}
            onChange={(e) => setSector(e.target.value)}
            placeholder="Ex. Informatique, BTP…"
          />
        </label>
        <label className="check" style={{ alignSelf: "end" }}>
          <input
            type="checkbox"
            checked={verifiedOnly}
            onChange={(e) => setVerifiedOnly(e.target.checked)}
          />
          Profils vérifiés uniquement
        </label>
      </div>

      <ErrorNote error={error} />

      {candidates.length === 0 && (
        <Empty title="Aucun profil ne correspond">
          <p>Élargissez les compétences recherchées ou désactivez le filtre « vérifiés uniquement ».</p>
        </Empty>
      )}

      {candidates.map((c) => (
        <CandidateCard key={c.user_id} candidate={c} onContact={contact} onAddToShortlist={addToShortlist} />
      ))}
    </div>
  );
}
