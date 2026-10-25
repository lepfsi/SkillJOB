import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client.js";

// Référentiel commun GET /api/domains. Le cache module évite de recharger
// l'arbre à chaque formulaire (profil, offre, filtres recruteur).
let cached = null;
let pending = null;

export function useDomains() {
  const [domains, setDomains] = useState(cached || []);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    if (cached) return undefined;
    if (!pending) {
      pending = api("/domains").catch((err) => {
        pending = null;
        throw err;
      });
    }
    pending
      .then((rows) => {
        cached = rows || [];
        if (alive) setDomains(cached);
      })
      .catch((err) => {
        if (alive) setError(err.detail || "Référentiel indisponible");
      });
    return () => {
      alive = false;
    };
  }, []);

  return { domains, error };
}

export function DomainPicker({
  domainId = null,
  specialtyIds = [],
  onChange,
  multiple = true,
  domainLabel = "Domaine",
  specialtyLabel = "Spécialités associées",
  showOther = false,
  otherValue = "",
  onOtherChange = null,
  hint = "",
}) {
  const { domains, error } = useDomains();
  const numericDomain = domainId === "" || domainId == null ? null : Number(domainId);
  const selected = useMemo(
    () => domains.find((domain) => domain.id === numericDomain) || null,
    [domains, numericDomain],
  );
  const current = useMemo(
    () => new Set((specialtyIds || []).map((id) => Number(id))),
    [specialtyIds],
  );

  function changeDomain(value) {
    const nextId = value ? Number(value) : null;
    const nextDomain = domains.find((domain) => domain.id === nextId);
    const allowed = new Set((nextDomain?.specialties || []).map((item) => item.id));
    const kept = (specialtyIds || []).filter((id) => allowed.has(Number(id)));
    onChange?.({
      domain_id: nextId,
      specialty_ids: multiple ? kept : [],
    });
  }

  function toggleSpecialty(id) {
    const value = Number(id);
    const next = current.has(value)
      ? (specialtyIds || []).filter((item) => Number(item) !== value)
      : [...(specialtyIds || []), value];
    onChange?.({ domain_id: numericDomain, specialty_ids: next });
  }

  function changeSpecialty(value) {
    onChange?.({
      domain_id: numericDomain,
      specialty_ids: value ? [Number(value)] : [],
    });
  }

  return (
    <div className="domain-picker">
      <label className="field">
        <span>{domainLabel}</span>
        <select value={numericDomain ?? ""} onChange={(e) => changeDomain(e.target.value)}>
          <option value="">Choisir un domaine</option>
          {domains.map((domain) => (
            <option key={domain.id} value={domain.id}>
              {domain.name}
            </option>
          ))}
        </select>
      </label>

      {selected && (
        multiple ? (
          <fieldset className="domain-specialties">
            <legend>{specialtyLabel}</legend>
            {selected.specialties.length === 0 ? (
              <p className="muted small">Aucune spécialité dans ce domaine.</p>
            ) : (
              <div className="domain-specialty-grid">
                {selected.specialties.map((specialty) => (
                  <label className="check" key={specialty.id}>
                    <input
                      type="checkbox"
                      checked={current.has(specialty.id)}
                      onChange={() => toggleSpecialty(specialty.id)}
                    />
                    {specialty.name}
                  </label>
                ))}
              </div>
            )}
          </fieldset>
        ) : (
          <label className="field">
            <span>{specialtyLabel}</span>
            <select
              value={(specialtyIds || [])[0] ?? ""}
              onChange={(e) => changeSpecialty(e.target.value)}
            >
              <option value="">Toutes les spécialités du domaine</option>
              {selected.specialties.map((specialty) => (
                <option key={specialty.id} value={specialty.id}>
                  {specialty.name}
                </option>
              ))}
            </select>
          </label>
        )
      )}

      {showOther && selected?.slug === "autres" && (
        <label className="field">
          <span>Précisez votre domaine ou spécialité</span>
          <input
            value={otherValue || ""}
            onChange={(e) => onOtherChange?.(e.target.value)}
            placeholder="Ex. métier émergent, activité non listée"
          />
        </label>
      )}

      {hint && <p className="muted small">{hint}</p>}
      {error && <p className="alert alert-error small">{error}</p>}
    </div>
  );
}
