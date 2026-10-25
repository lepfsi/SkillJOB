import { useEffect, useMemo, useState } from "react";
import { api } from "../../api/client.js";
import { Loader, ErrorNote } from "../../components/ui.jsx";

// Référentiel commun des domaines et spécialités. Le même arbre alimente
// le profil candidat, les offres, les filtres publics et la recherche
// recruteur. Les suppressions sont des désactivations : une offre ou un
// profil qui cite une entrée ne casse jamais.

const EMPTY_DOMAIN = {
  name: "",
  description: "",
  aliases: "",
  sort_order: 0,
  active: true,
};

const EMPTY_SPECIALTY = {
  name: "",
  description: "",
  aliases: "",
  sort_order: 0,
  active: true,
};

function listToText(values) {
  return (values || []).join(", ");
}

function textToList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function AdminDomains() {
  const [domains, setDomains] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [domainForm, setDomainForm] = useState(EMPTY_DOMAIN);
  const [specialtyForm, setSpecialtyForm] = useState(EMPTY_SPECIALTY);
  const [editingSpecialty, setEditingSpecialty] = useState(null);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh(keepSelection = true) {
    const rows = await api("/admin/domains");
    setDomains(rows || []);
    if (keepSelection && selectedId != null) {
      const current = (rows || []).find((row) => row.id === selectedId);
      if (current) fillDomain(current);
    }
    return rows || [];
  }

  function fillDomain(domain) {
    setSelectedId(domain.id);
    setDomainForm({
      name: domain.name,
      description: domain.description || "",
      aliases: listToText(domain.aliases),
      sort_order: domain.sort_order || 0,
      active: domain.active !== false,
    });
    setEditingSpecialty(null);
    setSpecialtyForm(EMPTY_SPECIALTY);
  }

  useEffect(() => {
    api("/admin/domains")
      .then((rows) => {
        setDomains(rows || []);
        if ((rows || []).length > 0) fillDomain(rows[0]);
      })
      .catch((err) => setError(err.detail));
  }, []);

  const selected = useMemo(
    () => (domains || []).find((domain) => domain.id === selectedId) || null,
    [domains, selectedId],
  );

  function startNewDomain() {
    setSelectedId(null);
    setDomainForm(EMPTY_DOMAIN);
    setEditingSpecialty(null);
    setSpecialtyForm(EMPTY_SPECIALTY);
  }

  async function saveDomain(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setFlash("");
    const body = {
      ...domainForm,
      aliases: textToList(domainForm.aliases),
      sort_order: Number(domainForm.sort_order) || 0,
    };
    try {
      let saved;
      if (selectedId == null) {
        saved = await api("/admin/domains", { method: "POST", body });
        setSelectedId(saved.id);
      } else {
        saved = await api(`/admin/domains/${selectedId}`, { method: "PUT", body });
      }
      await refresh(false);
      fillDomain(saved);
      setFlash("Domaine enregistré.");
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function deactivateDomain() {
    if (selectedId == null) return;
    if (!window.confirm("Désactiver ce domaine ? Il ne sera plus proposé dans les formulaires.")) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(`/admin/domains/${selectedId}`, { method: "DELETE" });
      const rows = await refresh(false);
      if (rows.length) fillDomain(rows[0]);
      else startNewDomain();
      setFlash("Domaine désactivé. Les offres existantes sont conservées.");
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  function editSpecialty(specialty) {
    setEditingSpecialty(specialty.id);
    setSpecialtyForm({
      name: specialty.name,
      description: specialty.description || "",
      aliases: listToText(specialty.aliases),
      sort_order: specialty.sort_order || 0,
      active: specialty.active !== false,
    });
  }

  function newSpecialty() {
    setEditingSpecialty(null);
    setSpecialtyForm(EMPTY_SPECIALTY);
  }

  async function saveSpecialty(event) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError("");
    setFlash("");
    const body = {
      ...specialtyForm,
      aliases: textToList(specialtyForm.aliases),
      sort_order: Number(specialtyForm.sort_order) || 0,
    };
    try {
      let saved;
      if (editingSpecialty == null) {
        saved = await api(`/admin/domains/${selected.id}/specialties`, {
          method: "POST",
          body,
        });
      } else {
        saved = await api(`/admin/domains/${selected.id}/specialties/${editingSpecialty}`, {
          method: "PUT",
          body,
        });
      }
      await refresh(false);
      fillDomain(selected);
      editSpecialty(saved);
      setFlash("Spécialité enregistrée.");
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function deactivateSpecialty(specialty) {
    if (!selected) return;
    if (!window.confirm(`Désactiver « ${specialty.name} » ?`)) return;
    setBusy(true);
    setError("");
    try {
      await api(`/admin/domains/${selected.id}/specialties/${specialty.id}`, {
        method: "DELETE",
      });
      await refresh(false);
      fillDomain(selected);
      setFlash("Spécialité désactivée.");
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  if (error && !domains) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!domains) {
    return <div className="page"><Loader /></div>;
  }

  return (
    <div className="page">
      <h1>Domaines et spécialités</h1>
      <p className="page-lead">
        Ce référentiel est commun au profil candidat, aux offres, aux filtres
        publics et à la recherche de talents. Préchargez les domaines et les
        spécialités de votre marché ; les candidats et recruteurs les
        retrouvent ensuite dans des listes homogènes.
      </p>
      <ErrorNote error={error} />
      {flash && <div className="alert alert-success">{flash}</div>}

      <div className="domain-admin">
        <aside className="panel domain-admin-list" aria-label="Domaines">
          <div className="domain-admin-list-head">
            <h2>Domaines</h2>
            <button className="btn btn-outline btn-small" type="button" onClick={startNewDomain}>
              Ajouter
            </button>
          </div>
          {domains.map((domain) => (
            <button
              key={domain.id}
              type="button"
              className={`domain-admin-pick${domain.id === selectedId ? " is-active" : ""}`}
              onClick={() => fillDomain(domain)}
            >
              <span>{domain.name}</span>
              <small>
                {domain.specialties.length} spécialité{domain.specialties.length > 1 ? "s" : ""}
                {domain.active === false ? " · inactive" : ""}
              </small>
            </button>
          ))}
          {domains.length === 0 && <p className="muted small">Aucun domaine.</p>}
        </aside>

        <div className="domain-admin-detail">
          <form className="panel" onSubmit={saveDomain}>
            <h2>{selectedId == null ? "Nouveau domaine" : `Modifier ${selected?.name || "le domaine"}`}</h2>
            <div className="grid-2">
              <label className="field">
                <span>Nom du domaine *</span>
                <input
                  value={domainForm.name}
                  onChange={(e) => setDomainForm({ ...domainForm, name: e.target.value })}
                  required
                  placeholder="Ex. Informatique et numérique"
                />
              </label>
              <label className="field">
                <span>Ordre d'affichage</span>
                <input
                  type="number"
                  value={domainForm.sort_order}
                  onChange={(e) => setDomainForm({ ...domainForm, sort_order: e.target.value })}
                />
              </label>
            </div>
            <label className="field">
              <span>Description</span>
              <textarea
                rows="2"
                value={domainForm.description}
                onChange={(e) => setDomainForm({ ...domainForm, description: e.target.value })}
              />
            </label>
            <label className="field">
              <span>Synonymes (séparés par des virgules)</span>
              <input
                value={domainForm.aliases}
                onChange={(e) => setDomainForm({ ...domainForm, aliases: e.target.value })}
                placeholder="Informatique / IT, IT, Numérique"
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={domainForm.active}
                onChange={(e) => setDomainForm({ ...domainForm, active: e.target.checked })}
              />
              Domaine actif (visible dans les formulaires)
            </label>
            <div className="actions-row">
              <button className="btn btn-primary" disabled={busy}>
                {busy ? "Enregistrement…" : "Enregistrer le domaine"}
              </button>
              {selectedId != null && selected?.active !== false && (
                <button type="button" className="btn btn-ghost" onClick={deactivateDomain} disabled={busy}>
                  Désactiver
                </button>
              )}
            </div>
          </form>

          {selected && (
            <div className="panel domain-admin-specialties">
              <div className="domain-admin-list-head">
                <div>
                  <h2>Spécialités de {selected.name}</h2>
                  <p className="muted small">
                    Les candidats en choisissent plusieurs ; les recruteurs peuvent
                    filtrer sur l'une d'elles.
                  </p>
                </div>
                <button className="btn btn-outline btn-small" type="button" onClick={newSpecialty}>
                  Nouvelle spécialité
                </button>
              </div>

              <div className="domain-admin-specialty-list">
                {selected.specialties.map((specialty) => (
                  <div className="domain-admin-specialty" key={specialty.id}>
                    <div>
                      <strong>{specialty.name}</strong>
                      {specialty.description && <p className="muted small">{specialty.description}</p>}
                      {specialty.active === false && <span className="chip chip-soft">Inactive</span>}
                    </div>
                    <div className="domain-admin-specialty-actions">
                      <button type="button" className="btn btn-ghost btn-small" onClick={() => editSpecialty(specialty)}>
                        Modifier
                      </button>
                      {specialty.active !== false && (
                        <button
                          type="button"
                          className="btn btn-ghost btn-small"
                          onClick={() => deactivateSpecialty(specialty)}
                          disabled={busy}
                        >
                          Désactiver
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                {selected.specialties.length === 0 && (
                  <p className="muted small">Aucune spécialité pour ce domaine.</p>
                )}
              </div>

              <form className="domain-admin-specialty-form" onSubmit={saveSpecialty}>
                <h3>{editingSpecialty == null ? "Ajouter une spécialité" : "Modifier la spécialité"}</h3>
                <div className="grid-2">
                  <label className="field">
                    <span>Nom *</span>
                    <input
                      value={specialtyForm.name}
                      onChange={(e) => setSpecialtyForm({ ...specialtyForm, name: e.target.value })}
                      required
                      placeholder="Ex. Cybersécurité"
                    />
                  </label>
                  <label className="field">
                    <span>Ordre d'affichage</span>
                    <input
                      type="number"
                      value={specialtyForm.sort_order}
                      onChange={(e) => setSpecialtyForm({ ...specialtyForm, sort_order: e.target.value })}
                    />
                  </label>
                </div>
                <label className="field">
                  <span>Synonymes (séparés par des virgules)</span>
                  <input
                    value={specialtyForm.aliases}
                    onChange={(e) => setSpecialtyForm({ ...specialtyForm, aliases: e.target.value })}
                  />
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={specialtyForm.active}
                    onChange={(e) => setSpecialtyForm({ ...specialtyForm, active: e.target.checked })}
                  />
                  Spécialité active
                </label>
                <div className="actions-row">
                  <button className="btn btn-primary btn-small" disabled={busy}>
                    {editingSpecialty == null ? "Ajouter" : "Mettre à jour"}
                  </button>
                  {editingSpecialty != null && (
                    <button type="button" className="btn btn-ghost btn-small" onClick={newSpecialty}>
                      Annuler
                    </button>
                  )}
                </div>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
