import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { INSTITUTION_LABELS, ENTREPRENEUR_KIND_LABELS } from "../../lib.js";
import { Loader, ErrorNote, Empty } from "../../components/ui.jsx";

// Gestion des contenus publics : Programmes publics (FNE, MINFOP, MINPME,
// concours) et ressources Entrepreneuriat. CRUD complet côté admin.

// Sous-catégories du référentiel (miroir de app/api/referentiels.py) :
// l'administration range ses ajouts dans les mêmes dispositifs que les
// fiches existantes.
const SUBCATEGORY_OPTIONS = [
  "", "concours_direct", "concours_integration", "universites", "ecoles",
  "avis_concours", "fne", "bourse_formation", "ong_emplois", "ong_stages",
  "armee", "gendarmerie", "bir", "garde_presidentielle", "emia",
  "armee_etrangere", "police", "appels_minader", "appels_minepat",
  "appels_minjec", "appels_mintoul", "appels_minfof", "appels_mincom",
];

const SUBCATEGORY_LABELS = {
  "": "Aucune",
  concours_direct: "Concours directs",
  concours_integration: "Concours d'intégration",
  universites: "Universités d'État",
  ecoles: "Écoles de formation par université",
  avis_concours: "Avis de concours",
  fne: "Fonds National de l'Emploi (FNE)",
  bourse_formation: "Bourses de formation professionnelle",
  ong_emplois: "Offres d'emploi des ONG",
  ong_stages: "Programmes de stage des ONG",
  armee: "Concours d'entrée dans l'armée",
  gendarmerie: "Gendarmerie nationale",
  bir: "Bataillon d'intervention rapide (BIR)",
  garde_presidentielle: "Garde présidentielle",
  emia: "École militaire interarmes (EMIA)",
  armee_etrangere: "Armée étrangère",
  police: "Concours d'entrée à la police nationale",
  appels_minader: "Appels à projets · MINADER (agriculture)",
  appels_minepat: "Appels à projets · MINEPAT (planification)",
  appels_minjec: "Appels à projets · MINJEC (jeunesse)",
  appels_mintoul: "Appels à projets · MINTOUL (tourisme)",
  appels_minfof: "Appels à projets · MINFOF (forêts et faune)",
  appels_mincom: "Appels à projets · MINCOM (communication)",
};

const EMPTY_PROGRAM = {
  category: "minfopra",
  subcategory: "",
  title: "",
  description: "",
  eligibility: "",
  url: "",
  deadline: "",
};

function InstitutionalTab() {
  const [items, setItems] = useState(null);
  const [form, setForm] = useState(null);
  const [pendingFile, setPendingFile] = useState(null);
  const [pendingLabel, setPendingLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const reload = () => {
    setForm(null);
    setPendingFile(null);
    setPendingLabel("");
    api("/admin/public-content/institutional")
      .then(setItems)
      .catch((e) => setError(e.detail));
  };

  useEffect(() => { reload(); }, []);

  function openNew() {
    setError("");
    setPendingFile(null);
    setPendingLabel("");
    setForm({ ...EMPTY_PROGRAM });
  }

  function openEdit(item) {
    setError("");
    setPendingFile(null);
    setPendingLabel("");
    setForm({ ...EMPTY_PROGRAM, ...item });
  }

  async function save(e) {
    e.preventDefault();
    if (
      form.id
      && form.source
      && form.source !== "admin"
      && !window.confirm(
        "Cette fiche vient du référentiel public. L'enregistrer la passera en « Administration » et la retirera de la synchronisation automatique. Continuer ?"
      )
    ) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      const body = {
        category: form.category,
        subcategory: form.subcategory || null,
        title: form.title,
        description: form.description || "",
        eligibility: form.eligibility || "",
        url: form.url || null,
        deadline: form.deadline || null,
      };
      let id = form.id;
      if (id) {
        await api(`/admin/public-content/institutional/${id}`, { method: "PUT", body });
      } else {
        const created = await api("/admin/public-content/institutional", {
          method: "POST", body,
        });
        id = created.id;
      }
      // PDF facultatif : joint APRÈS l'enregistrement de la fiche.
      if (pendingFile && id) {
        const fd = new FormData();
        fd.append("file", pendingFile);
        fd.append(
          "label",
          pendingLabel.trim() || pendingFile.name.replace(/\.pdf$/i, ""),
        );
        await api(`/admin/public-content/institutional/${id}/documents`, {
          method: "POST", form: fd,
        });
      }
      reload();
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function remove(item) {
    if (!window.confirm(`Supprimer « ${item.title} » ? Les PDF joints seront retirés.`)) return;
    try {
      await api(`/admin/public-content/institutional/${item.id}`, { method: "DELETE" });
      reload();
    } catch (err) {
      setError(err.detail);
    }
  }

  async function removeDoc(item, doc) {
    if (!window.confirm(`Retirer « ${doc.label} » du programme ?`)) return;
    try {
      await api(
        `/admin/public-content/institutional/${item.id}/documents/${doc.key}`,
        { method: "DELETE" },
      );
      const fresh = await api("/admin/public-content/institutional");
      setItems(fresh);
      if (form && form.id === item.id) {
        const updated = fresh.find((i) => i.id === item.id);
        setForm((f) => (f ? { ...f, documents: updated?.documents || [] } : f));
      }
    } catch (err) {
      setError(err.detail);
    }
  }

  if (!items) return <Loader />;

  return (
    <div>
      <div className="actions-row">
        <button className="btn btn-primary" onClick={openNew}>
          Nouveau programme public
        </button>
      </div>
      <ErrorNote error={error} />

      {form && (
        <form className="panel" onSubmit={save}>
          <h2>{form.id ? "Modifier le programme" : "Nouveau programme public"}</h2>
          {form.id && form.source !== "admin" && (
            <div className="alert alert-warning">
              Cette fiche est issue du référentiel public. L'enregistrer la
              passera en « Administration » : elle ne sera plus mise à jour par
              la synchronisation automatique. Les PDF joints sont conservés.
            </div>
          )}
          <div className="grid-2">
            <label className="field">
              <span>Institution *</span>
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                {Object.entries(INSTITUTION_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label className="field">
              <span>Dispositif (sous-catégorie)</span>
              <select value={form.subcategory || ""} onChange={(e) => setForm({ ...form, subcategory: e.target.value })}>
                {SUBCATEGORY_OPTIONS.map((s) => <option key={s} value={s}>{SUBCATEGORY_LABELS[s]}</option>)}
              </select>
            </label>
          </div>
          <label className="field">
            <span>Titre *</span>
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea rows="2" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </label>
          <div className="grid-2">
            <label className="field">
              <span>Éligibilité</span>
              <input value={form.eligibility} onChange={(e) => setForm({ ...form, eligibility: e.target.value })} />
            </label>
            <label className="field">
              <span>Calendrier</span>
              <input value={form.deadline} onChange={(e) => setForm({ ...form, deadline: e.target.value })} placeholder="Ex. Sessions annuelles" />
            </label>
          </div>
          <label className="field">
            <span>Lien officiel</span>
            <input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://…" />
          </label>

          {/* PDF officiels : facultatif, un ou plusieurs par programme. */}
          <fieldset className="admin-docs">
            <legend>Documents officiels (PDF), facultatif</legend>
            {form.id && (
              <div className="admin-doc-list">
                {(form.documents || []).length === 0 && (
                  <p className="small muted">Aucun PDF joint pour l'instant.</p>
                )}
                {(form.documents || []).map((doc) => (
                  <div className="admin-doc-row" key={doc.key}>
                    <span className="admin-doc-tag">PDF</span>
                    <a href={doc.url} download={`${doc.label}.pdf`}>{doc.label}</a>
                    <button
                      type="button"
                      className="btn btn-ghost btn-small"
                      onClick={() => removeDoc(form, doc)}
                    >
                      Retirer
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="admin-doc-add">
              <label className="field">
                <span>Joindre un PDF</span>
                <input
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={(e) => setPendingFile(e.target.files?.[0] || null)}
                />
              </label>
              <label className="field">
                <span>Libellé du document</span>
                <input
                  value={pendingLabel}
                  onChange={(e) => setPendingLabel(e.target.value)}
                  placeholder="Ex. Avis de concours 2026"
                />
              </label>
            </div>
            {pendingFile && (
              <p className="small muted">
                Sélection : {pendingFile.name} ({Math.round(pendingFile.size / 1024)} Ko)
                . Le PDF sera joint {form.id ? "immédiatement" : "après l'enregistrement"}.
              </p>
            )}
            <p className="small muted">
              PDF uniquement, 15 Mo maximum. Le fichier est hébergé tel quel et
              téléchargeable depuis la page Programmes publics.
            </p>
          </fieldset>

          <div className="actions-row">
            <button className="btn btn-primary" disabled={busy}>
              {busy ? "Enregistrement…" : "Enregistrer"}
            </button>
            <button type="button" className="btn btn-ghost" onClick={reload}>Annuler</button>
          </div>
        </form>
      )}

      {items.length === 0 && <Empty title="Aucun programme" />}
      {items.map((item) => (
        <div className="app-row" key={item.id}>
          <div className="app-head">
            <div>
              <strong>{item.title}</strong>
              <p className="job-meta" style={{ margin: "0.15rem 0" }}>
                {INSTITUTION_LABELS[item.category] || item.category}
                {item.subcategory && ` · ${SUBCATEGORY_LABELS[item.subcategory] || item.subcategory}`}
              </p>
              {(item.documents || []).length > 0 && (
                <div className="admin-doc-chips">
                  {item.documents.map((doc) => (
                    <a key={doc.key} href={doc.url} download={`${doc.label}.pdf`} className="admin-doc-chip">
                      <span>PDF</span> {doc.label}
                    </a>
                  ))}
                </div>
              )}
            </div>
            <div className="actions-row" style={{ marginTop: 0 }}>
              <span
                className={`badge ${item.source === "admin" ? "badge-strong" : "badge-medium"}`}
                title={item.source === "admin"
                  ? "Fiche gérée par l'administration."
                  : "Fiche synchronisée depuis le référentiel public : toute modification la passera en Administration."}
              >
                {item.source === "admin" ? "Administration" : "Référentiel"}
              </span>
              <button className="btn btn-ghost btn-small" onClick={() => openEdit(item)}>Modifier</button>
              <button className="btn btn-remove btn-small" onClick={() => remove(item)}>Supprimer</button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

const EMPTY_UNIVERSITY = {
  name: "",
  slug: "",
  short_name: "",
  city: "",
  region: "",
  description: "",
  website: "",
  source_url: "",
  sort_order: 0,
};

const EMPTY_SCHOOL = {
  name: "",
  short_name: "",
  kind: "Grande école",
  admission: "Concours d'entrée",
  eligibility: "",
  url: "",
  deadline: "",
  sort_order: 0,
};

// Catalogue MINESUP : les universités, puis leurs grandes écoles. Le
// seed de démarrage ne s'exécute que sur une base vide : toutes les
// corrections faites ici sont conservées.
function MinesupTab() {
  const [items, setItems] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [uniForm, setUniForm] = useState(null);
  const [schoolForm, setSchoolForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function reload(preferId = null) {
    setError("");
    try {
      const list = await api("/admin/public-content/minesup");
      setItems(list);
      setSelectedId((current) => {
        const wanted = preferId ?? current;
        if (list.some((university) => university.id === wanted)) return wanted;
        return list[0]?.id ?? null;
      });
    } catch (err) {
      setError(err.detail);
    }
  }

  useEffect(() => { reload(); }, []);

  const selected = (items || []).find(
    (university) => university.id === selectedId,
  ) || null;

  function openNewUniversity() {
    setError("");
    setUniForm({ ...EMPTY_UNIVERSITY });
    setSchoolForm(null);
  }

  function openEditUniversity(university) {
    setError("");
    setUniForm({
      id: university.id,
      name: university.name,
      slug: university.slug,
      short_name: university.short_name,
      city: university.city,
      region: university.region,
      description: university.description,
      website: university.website || "",
      source_url: university.source_url || "",
      sort_order: university.sort_order,
    });
    setSchoolForm(null);
  }

  async function saveUniversity(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = {
        name: uniForm.name,
        slug: uniForm.slug || null,
        short_name: uniForm.short_name || "",
        city: uniForm.city || "",
        region: uniForm.region || "",
        description: uniForm.description || "",
        website: uniForm.website || null,
        source_url: uniForm.source_url || null,
        sort_order: Number(uniForm.sort_order) || 0,
      };
      let id = uniForm.id;
      if (id) {
        await api(`/admin/public-content/minesup/universities/${id}`, {
          method: "PUT", body,
        });
      } else {
        const created = await api("/admin/public-content/minesup/universities", {
          method: "POST", body,
        });
        id = created.id;
      }
      setUniForm(null);
      await reload(id);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function removeUniversity(university) {
    if (!window.confirm(
      `Supprimer « ${university.name} » et ses ${university.schools.length} école(s) ?`,
    )) return;
    setBusy(true);
    setError("");
    try {
      await api(`/admin/public-content/minesup/universities/${university.id}`, {
        method: "DELETE",
      });
      if (selectedId === university.id) {
        setSelectedId(null);
        setUniForm(null);
        setSchoolForm(null);
      }
      await reload();
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  function openNewSchool() {
    setError("");
    setSchoolForm({ ...EMPTY_SCHOOL });
  }

  function openEditSchool(school) {
    setError("");
    setSchoolForm({
      id: school.id,
      name: school.name,
      short_name: school.short_name,
      kind: school.kind,
      admission: school.admission,
      eligibility: school.eligibility,
      url: school.url || "",
      deadline: school.deadline || "",
      sort_order: school.sort_order ?? 0,
    });
  }

  async function saveSchool(e) {
    e.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const body = {
        name: schoolForm.name,
        short_name: schoolForm.short_name || "",
        kind: schoolForm.kind || "Grande école",
        admission: schoolForm.admission || "",
        eligibility: schoolForm.eligibility || "",
        url: schoolForm.url || null,
        deadline: schoolForm.deadline || null,
        sort_order: Number(schoolForm.sort_order) || 0,
      };
      if (schoolForm.id) {
        await api(`/admin/public-content/minesup/schools/${schoolForm.id}`, {
          method: "PUT", body,
        });
      } else {
        await api(
          `/admin/public-content/minesup/universities/${selected.id}/schools`,
          { method: "POST", body },
        );
      }
      setSchoolForm(null);
      await reload(selected.id);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function removeSchool(school) {
    if (!window.confirm(`Supprimer « ${school.name} » ?`)) return;
    setBusy(true);
    setError("");
    try {
      await api(`/admin/public-content/minesup/schools/${school.id}`, {
        method: "DELETE",
      });
      if (schoolForm?.id === school.id) setSchoolForm(null);
      await reload(selected?.id);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  if (!items) return <Loader />;

  return (
    <div>
      <div className="actions-row">
        <button type="button" className="btn btn-primary" onClick={openNewUniversity}>
          Nouvelle université
        </button>
        <span className="small muted">
          {items.length} université{items.length > 1 ? "s" : ""} ·{" "}
          {items.reduce((sum, university) => sum + university.schools.length, 0)} écoles
        </span>
      </div>
      <ErrorNote error={error} />

      {uniForm && (
        <form className="panel minesup-admin-form" onSubmit={saveUniversity}>
          <h2>{uniForm.id ? "Modifier l'université" : "Nouvelle université"}</h2>
          <div className="grid-2">
            <label className="field">
              <span>Nom officiel *</span>
              <input
                value={uniForm.name}
                onChange={(e) => setUniForm({ ...uniForm, name: e.target.value })}
                required
              />
            </label>
            <label className="field">
              <span>Sigle</span>
              <input
                value={uniForm.short_name}
                onChange={(e) => setUniForm({ ...uniForm, short_name: e.target.value })}
                placeholder="Ex. UY1"
              />
            </label>
          </div>
          <div className="grid-2">
            <label className="field">
              <span>Ville</span>
              <input
                value={uniForm.city}
                onChange={(e) => setUniForm({ ...uniForm, city: e.target.value })}
              />
            </label>
            <label className="field">
              <span>Région</span>
              <input
                value={uniForm.region}
                onChange={(e) => setUniForm({ ...uniForm, region: e.target.value })}
              />
            </label>
          </div>
          <label className="field">
            <span>Description</span>
            <textarea
              rows="2"
              value={uniForm.description}
              onChange={(e) => setUniForm({ ...uniForm, description: e.target.value })}
            />
          </label>
          <div className="grid-2">
            <label className="field">
              <span>Site officiel</span>
              <input
                value={uniForm.website}
                onChange={(e) => setUniForm({ ...uniForm, website: e.target.value })}
                placeholder="https://…"
              />
            </label>
            <label className="field">
              <span>Page source MINESUP</span>
              <input
                value={uniForm.source_url}
                onChange={(e) => setUniForm({ ...uniForm, source_url: e.target.value })}
                placeholder="https://…"
              />
            </label>
          </div>
          <div className="grid-2">
            <label className="field">
              <span>Identifiant d'URL</span>
              <input
                value={uniForm.slug}
                onChange={(e) => setUniForm({ ...uniForm, slug: e.target.value })}
                placeholder="Généré depuis le nom si vide"
              />
            </label>
            <label className="field">
              <span>Ordre d'affichage</span>
              <input
                type="number"
                value={uniForm.sort_order}
                onChange={(e) => setUniForm({ ...uniForm, sort_order: e.target.value })}
              />
            </label>
          </div>
          <div className="actions-row">
            <button className="btn btn-primary" disabled={busy}>
              {busy ? "Enregistrement…" : "Enregistrer"}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setUniForm(null)}>
              Annuler
            </button>
          </div>
        </form>
      )}

      {items.length === 0 ? (
        <Empty title="Aucune université">
          <p>Ajoutez une première université pour construire l'explorateur MINESUP.</p>
        </Empty>
      ) : (
        <div className="minesup-admin">
          <aside className="minesup-admin-list" aria-label="Universités MINESUP">
            {items.map((university) => (
              <button
                type="button"
                key={university.id}
                className={`minesup-admin-pick${university.id === selectedId ? " is-active" : ""}`}
                onClick={() => {
                  setSelectedId(university.id);
                  setSchoolForm(null);
                }}
              >
                <span className="minesup-admin-pick-name">{university.name}</span>
                <span className="minesup-admin-pick-meta">
                  {[university.short_name, university.city]
                    .filter(Boolean).join(" · ") || "Ville à compléter"}
                </span>
                <span className="minesup-admin-pick-count">
                  {university.schools.length} école{university.schools.length > 1 ? "s" : ""}
                  {university.source === "admin" && " · corrigée"}
                </span>
              </button>
            ))}
          </aside>

          <div className="minesup-admin-detail">
            {!selected ? (
              <Empty title="Choisissez une université" />
            ) : (
              <>
                <div className="minesup-admin-head">
                  <div>
                    <span className="minesup-eyebrow">Université MINESUP</span>
                    <h2>{selected.name}</h2>
                    <p className="small muted">
                      {[selected.short_name, selected.city, selected.region]
                        .filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  <div className="actions-row" style={{ marginTop: 0 }}>
                    <button
                      type="button"
                      className="btn btn-ghost btn-small"
                      onClick={() => openEditUniversity(selected)}
                    >
                      Modifier
                    </button>
                    <button
                      type="button"
                      className="btn btn-remove btn-small"
                      onClick={() => removeUniversity(selected)}
                      disabled={busy}
                    >
                      Supprimer
                    </button>
                  </div>
                </div>

                {selected.description && (
                  <p className="minesup-admin-desc">{selected.description}</p>
                )}
                {(selected.website || selected.source_url) && (
                  <p className="small">
                    {selected.website && (
                      <a href={selected.website} target="_blank" rel="noreferrer">
                        Site officiel
                      </a>
                    )}
                    {selected.website && selected.source_url && " · "}
                    {selected.source_url && (
                      <a href={selected.source_url} target="_blank" rel="noreferrer">
                        Source MINESUP
                      </a>
                    )}
                  </p>
                )}

                <div className="minesup-schools-head">
                  <div>
                    <h3>Écoles et concours</h3>
                    <p className="small muted">
                      {selected.schools.length} fiche{selected.schools.length > 1 ? "s" : ""} rattachée{selected.schools.length > 1 ? "s" : ""}
                    </p>
                  </div>
                  <button type="button" className="btn btn-outline btn-small" onClick={openNewSchool}>
                    Ajouter une école
                  </button>
                </div>

                {schoolForm && (
                  <form className="panel minesup-admin-form" onSubmit={saveSchool}>
                    <h2>{schoolForm.id ? "Modifier l'école" : "Nouvelle école"}</h2>
                    <label className="field">
                      <span>Nom officiel *</span>
                      <input
                        value={schoolForm.name}
                        onChange={(e) => setSchoolForm({ ...schoolForm, name: e.target.value })}
                        required
                      />
                    </label>
                    <div className="grid-2">
                      <label className="field">
                        <span>Sigle</span>
                        <input
                          value={schoolForm.short_name}
                          onChange={(e) => setSchoolForm({ ...schoolForm, short_name: e.target.value })}
                        />
                      </label>
                      <label className="field">
                        <span>Type</span>
                        <input
                          value={schoolForm.kind}
                          onChange={(e) => setSchoolForm({ ...schoolForm, kind: e.target.value })}
                          placeholder="Ex. Grande école d'ingénieurs"
                        />
                      </label>
                    </div>
                    <div className="grid-2">
                      <label className="field">
                        <span>Voie d'admission</span>
                        <input
                          value={schoolForm.admission}
                          onChange={(e) => setSchoolForm({ ...schoolForm, admission: e.target.value })}
                        />
                      </label>
                      <label className="field">
                        <span>Calendrier annoncé</span>
                        <input
                          value={schoolForm.deadline}
                          onChange={(e) => setSchoolForm({ ...schoolForm, deadline: e.target.value })}
                          placeholder="Ex. Session annuelle publiée par le MINESUP"
                        />
                      </label>
                    </div>
                    <label className="field">
                      <span>Éligibilité</span>
                      <textarea
                        rows="2"
                        value={schoolForm.eligibility}
                        onChange={(e) => setSchoolForm({ ...schoolForm, eligibility: e.target.value })}
                        placeholder="Diplôme, série, cycle visé, selon l'avis annuel…"
                      />
                    </label>
                    <div className="grid-2">
                      <label className="field">
                        <span>Lien officiel</span>
                        <input
                          value={schoolForm.url}
                          onChange={(e) => setSchoolForm({ ...schoolForm, url: e.target.value })}
                          placeholder="https://…"
                        />
                      </label>
                      <label className="field">
                        <span>Ordre d'affichage</span>
                        <input
                          type="number"
                          value={schoolForm.sort_order}
                          onChange={(e) => setSchoolForm({ ...schoolForm, sort_order: e.target.value })}
                        />
                      </label>
                    </div>
                    <div className="actions-row">
                      <button className="btn btn-primary" disabled={busy}>
                        {busy ? "Enregistrement…" : "Enregistrer"}
                      </button>
                      <button type="button" className="btn btn-ghost" onClick={() => setSchoolForm(null)}>
                        Annuler
                      </button>
                    </div>
                  </form>
                )}

                {selected.schools.length === 0 ? (
                  <Empty title="Aucune école rattachée">
                    <p>Ajoutez les grandes écoles et concours de cette université.</p>
                  </Empty>
                ) : (
                  <div className="minesup-admin-schools">
                    {selected.schools.map((school) => (
                      <article key={school.id} className="minesup-admin-school">
                        <div>
                          <span className="minesup-school-kind">{school.kind}</span>
                          <strong>{school.name}</strong>
                          <p className="small muted">
                            {[school.short_name, school.admission]
                              .filter(Boolean).join(" · ")}
                          </p>
                        </div>
                        <div className="actions-row" style={{ marginTop: 0 }}>
                          <button
                            type="button"
                            className="btn btn-ghost btn-small"
                            onClick={() => openEditSchool(school)}
                          >
                            Modifier
                          </button>
                          <button
                            type="button"
                            className="btn btn-remove btn-small"
                            onClick={() => removeSchool(school)}
                            disabled={busy}
                          >
                            Supprimer
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function EntrepreneurTab() {
  const [items, setItems] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");

  const reload = () => {
    setForm(null);
    api("/admin/public-content/entrepreneurship")
      .then(setItems)
      .catch((e) => setError(e.detail));
  };

  useEffect(() => { reload(); }, []);

  async function save(e) {
    e.preventDefault();
    try {
      const body = {
        ...form,
        sectors: (form.sectors_str || "").split(",").map((s) => s.trim()).filter(Boolean),
      };
      delete body.sectors_str;
      if (form.id) {
        await api(`/admin/public-content/entrepreneurship/${form.id}`, { method: "PUT", body });
      } else {
        await api("/admin/public-content/entrepreneurship", { method: "POST", body });
      }
      reload();
    } catch (err) {
      setError(err.detail);
    }
  }

  async function remove(item) {
    if (!window.confirm(`Supprimer « ${item.title} » ?`)) return;
    try {
      await api(`/admin/public-content/entrepreneurship/${item.id}`, { method: "DELETE" });
      reload();
    } catch (err) {
      setError(err.detail);
    }
  }

  if (!items) return <Loader />;

  return (
    <div>
      <div className="actions-row">
        <button className="btn btn-primary" onClick={() => setForm({
          kind: "concours", title: "", description: "",
          organizer: "", url: "", sectors_str: "",
        })}>
          Nouvelle ressource entrepreneuriat
        </button>
      </div>
      {form && (
        <form className="panel" onSubmit={save}>
          <h2>{form.id ? "Modifier la ressource" : "Nouvelle ressource"}</h2>
          <div className="grid-2">
            <label className="field">
              <span>Type *</span>
              <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
                {Object.entries(ENTREPRENEUR_KIND_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label className="field">
              <span>Organisateur</span>
              <input value={form.organizer} onChange={(e) => setForm({ ...form, organizer: e.target.value })} />
            </label>
          </div>
          <label className="field">
            <span>Titre *</span>
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea rows="2" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </label>
          <div className="grid-2">
            <label className="field">
              <span>Lien</span>
              <input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://…" />
            </label>
            <label className="field">
              <span>Secteurs (séparés par des virgules)</span>
              <input
                value={form.sectors_str ?? (form.sectors || []).join(", ")}
                onChange={(e) => setForm({ ...form, sectors_str: e.target.value })}
                placeholder="Ex. Numérique, Agriculture"
              />
            </label>
          </div>
          <div className="actions-row">
            <button className="btn btn-primary">Enregistrer</button>
            <button type="button" className="btn btn-ghost" onClick={() => setForm(null)}>Annuler</button>
          </div>
        </form>
      )}
      {items.length === 0 && <Empty title="Aucune ressource" />}
      {items.map((item) => (
        <div className="app-row" key={item.id}>
          <div className="app-head">
            <div>
              <strong>{item.title}</strong>
              <p className="job-meta" style={{ margin: "0.15rem 0" }}>
                {ENTREPRENEUR_KIND_LABELS[item.kind] || item.kind}
                {item.organizer ? ` · ${item.organizer}` : ""}
              </p>
            </div>
            <div className="actions-row" style={{ marginTop: 0 }}>
              <button className="btn btn-ghost btn-small" onClick={() => setForm({ ...item, sectors_str: (item.sectors || []).join(", ") })}>Modifier</button>
              <button className="btn btn-remove btn-small" onClick={() => remove(item)}>Supprimer</button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function AdminPublicContent() {
  const [tab, setTab] = useState("institutional");

  return (
    <div className="page">
      <h1>Programmes publics & entrepreneuriat</h1>
      <p className="page-lead">
        Gestion des contenus affichés aux jeunes : concours, bourses,
        accompagnements ministériels et ressources entrepreneuriat.
      </p>
      <ErrorNote error={null} />
      <div className="doc-filters" style={{ marginTop: "1rem" }}>
        <button
          type="button"
          className={`doc-filter ${tab === "institutional" ? "active" : ""}`}
          onClick={() => setTab("institutional")}
        >
          Programmes publics
        </button>
        <button
          type="button"
          className={`doc-filter ${tab === "minesup" ? "active" : ""}`}
          onClick={() => setTab("minesup")}
        >
          Universités MINESUP
        </button>
        <button
          type="button"
          className={`doc-filter ${tab === "entrepreneurship" ? "active" : ""}`}
          onClick={() => setTab("entrepreneurship")}
        >
          Entrepreneuriat
        </button>
      </div>
      {tab === "institutional" && <InstitutionalTab />}
      {tab === "minesup" && <MinesupTab />}
      {tab === "entrepreneurship" && <EntrepreneurTab />}
    </div>
  );
}
