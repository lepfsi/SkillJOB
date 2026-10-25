import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../../api/client.js";
import ContactDialog from "../../components/ContactDialog.jsx";
import ShortlistDialog from "../../components/ShortlistDialog.jsx";
import TalentCard from "../../components/TalentCard.jsx";
import TalentProfile from "../../components/TalentProfile.jsx";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";
import { useDomains } from "../../components/DomainPicker.jsx";

// Talent search (§21) : recherche par compétences avec matching
// explicable, et carte de profil : tout ce que voit le recruteur.

export default function RecruiterCandidates() {
  const [candidates, setCandidates] = useState(null);
  const [skills, setSkills] = useState("");
  const [q, setQ] = useState("");
  const [region, setRegion] = useState("");
  const [sector, setSector] = useState("");
  const [domainId, setDomainId] = useState("");
  const [specialtyId, setSpecialtyId] = useState("");
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const { domains } = useDomains();
  const [geoRegions, setGeoRegions] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [contactTarget, setContactTarget] = useState(null);
  const [shortlistTarget, setShortlistTarget] = useState(null);
  const { candidateId } = useParams();
  const navigate = useNavigate();

  const isDetail = !!candidateId;
  const selectedDomain = domains.find((d) => String(d.id) === String(domainId));

  useEffect(() => {
    if (isDetail) return;
    const params = new URLSearchParams();
    if (skills.trim()) params.set("skills", skills.trim());
    if (q.trim()) params.set("q", q.trim());
    if (region) params.set("region", region);
    if (sector.trim()) params.set("sector", sector.trim());
    if (domainId) params.set("domain_id", domainId);
    if (specialtyId) params.set("specialty_id", specialtyId);
    if (verifiedOnly) params.set("verified_only", "true");
    const timer = setTimeout(() => {
      api(`/recruiter/candidates?${params.toString()}`)
        .then(setCandidates)
        .catch((e) => setError(e.detail));
    }, 250);
    return () => clearTimeout(timer);
  }, [skills, q, region, sector, domainId, specialtyId, verifiedOnly, isDetail]);

  const [card, setCard] = useState(null);
  const [cardError, setCardError] = useState("");

  useEffect(() => {
    api("/geo").then((d) => setGeoRegions(d.regions || [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (!isDetail) return;
    setCard(null);
    api(`/recruiter/candidates/${candidateId}`)
      .then(setCard)
      .catch((e) => setCardError(e.detail));
  }, [candidateId, isDetail]);

  function shortlistAdded() {
    setNotice("Candidat ajouté à la shortlist.");
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
        <TalentProfile
          candidate={card}
          onContact={setContactTarget}
          onAddToShortlist={setShortlistTarget}
        />
        <p className="small muted">
          Le contact passe par la messagerie interne : les coordonnées du
          candidat ne sont jamais exposées dans la recherche.
        </p>
        {notice && <div className="alert alert-success">{notice}</div>}
        <ErrorNote error={error} />
        {contactTarget && (
          <ContactDialog candidate={contactTarget} onClose={() => setContactTarget(null)} />
        )}
        {shortlistTarget && (
          <ShortlistDialog
            candidate={shortlistTarget}
            onClose={() => setShortlistTarget(null)}
            onDone={shortlistAdded}
          />
        )}
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
          <span>Domaine recherché</span>
          <select
            value={domainId}
            onChange={(e) => {
              setDomainId(e.target.value);
              setSpecialtyId("");
            }}
          >
            <option value="">Tous les domaines</option>
            {domains.map((domain) => (
              <option key={domain.id} value={domain.id}>{domain.name}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Spécialité</span>
          <select
            value={specialtyId}
            onChange={(e) => setSpecialtyId(e.target.value)}
            disabled={!selectedDomain}
          >
            <option value="">Toutes les spécialités</option>
            {(selectedDomain?.specialties || []).map((specialty) => (
              <option key={specialty.id} value={specialty.id}>{specialty.name}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Secteur d'activité visé (libre)</span>
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
      {notice && <div className="alert alert-success">{notice}</div>}

      {candidates.length === 0 && (
        <Empty title="Aucun profil ne correspond">
          <p>Élargissez les compétences recherchées ou désactivez le filtre « vérifiés uniquement ».</p>
        </Empty>
      )}

      {candidates.map((c) => (
        <TalentCard
          key={c.user_id}
          candidate={c}
          profileHref={`/recruteur/candidats/${c.user_id}`}
          onContact={setContactTarget}
          onAddToShortlist={setShortlistTarget}
        />
      ))}

      {contactTarget && (
        <ContactDialog candidate={contactTarget} onClose={() => setContactTarget(null)} />
      )}
      {shortlistTarget && (
        <ShortlistDialog
          candidate={shortlistTarget}
          onClose={() => setShortlistTarget(null)}
          onDone={shortlistAdded}
        />
      )}
    </div>
  );
}
