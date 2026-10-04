// Éditeur de profil complet, partagé entre la validation du brouillon
// (DraftReview) et la page Profil. Sections dépliables pour une saisie
// fluide : on n'ouvre que ce qu'on modifie. Rien n'est enregistré tant
// que la page parente n'appelle pas PUT /api/profile.

import {
  EXPERIENCE_TYPE_LABELS,
  PROFICIENCY_LABELS,
  CONTRACT_TYPES,
} from "../lib.js";

function ListEditor({ items, onChange, blank, addLabel, render }) {
  return (
    <div className="list-editor">
      {(items || []).map((item, i) => (
        <div className="list-item panel-light" key={i}>
          {render(item, (patch) =>
            onChange(items.map((it, j) => (j === i ? { ...it, ...patch } : it)))
          )}
          <div className="list-item-footer">
            <button
              type="button"
              className="btn btn-remove btn-small"
              onClick={() => onChange(items.filter((_, j) => j !== i))}
            >
              Supprimer
            </button>
          </div>
        </div>
      ))}
      <button
        type="button"
        className="btn btn-outline btn-small"
        onClick={() => onChange([...(items || []), blank()])}
      >
        {addLabel}
      </button>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function Section({ title, hint, open = false, children }) {
  return (
    <details className="panel-light collapsible" open={open}>
      <summary><h3>{title}</h3></summary>
      {hint && <p className="muted small">{hint}</p>}
      {children}
    </details>
  );
}

export default function ProfileEditor({ profile, onChange }) {
  if (!profile) return null;
  const set = (field, value) => onChange({ ...profile, [field]: value });
  const prefs = profile.preferences || {
    sectors: [], target_roles: [], contract_types: [], remote_ok: false, linkedin_url: "",
  };
  const setPrefs = (patch) => onChange({ ...profile, preferences: { ...prefs, ...patch } });

  return (
    <div className="profile-editor">
      <Section title="Identité professionnelle" open>
        <div className="grid-2">
          <Field label="Titre professionnel (ex. Technicien support IT)">
            <input
              value={profile.title || ""}
              onChange={(e) => set("title", e.target.value)}
            />
          </Field>
          <Field label="Localisation (ville, région)">
            <input
              value={profile.location || ""}
              onChange={(e) => set("location", e.target.value)}
            />
          </Field>
          <Field label="Mobilité">
            <select
              value={profile.mobility || ""}
              onChange={(e) => set("mobility", e.target.value)}
            >
              <option value="">Non renseigné</option>
              <option>Ma ville uniquement</option>
              <option>National</option>
              <option>International</option>
            </select>
          </Field>
          <Field label="Disponibilité">
            <select
              value={profile.availability || ""}
              onChange={(e) => set("availability", e.target.value)}
            >
              <option value="">Non renseigné</option>
              <option>Immédiate</option>
              <option>Sous 1 mois</option>
              <option>Sous 3 mois</option>
            </select>
          </Field>
        </div>
        <Field label="Résumé professionnel">
          <textarea
            rows="3"
            value={profile.summary || ""}
            onChange={(e) => set("summary", e.target.value)}
            placeholder="Quelques phrases qui décrivent votre parcours et vos atouts."
          />
        </Field>
      </Section>

      <Section
        title="Expériences (formelles et informelles)"
        hint="Les petits boulots, missions, bénévolats et projets personnels comptent aussi : l'absence d'expérience formelle n'est pas une absence de compétence."
        open
      >
        <ListEditor
          items={profile.experiences || []}
          onChange={(v) => set("experiences", v)}
          addLabel="Ajouter une expérience"
          blank={() => ({
            title: "", organization: "", type: "formal",
            description: "", start_date: "", end_date: "", skills: [],
          })}
          render={(it, upd) => (
            <div className="grid-2">
              <Field label="Intitulé du poste ou de l'activité">
                <input value={it.title} onChange={(e) => upd({ title: e.target.value })} />
              </Field>
              <Field label="Structure / organisation">
                <input value={it.organization} onChange={(e) => upd({ organization: e.target.value })} />
              </Field>
              <Field label="Type d'expérience">
                <select value={it.type} onChange={(e) => upd({ type: e.target.value })}>
                  {Object.entries(EXPERIENCE_TYPE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </Field>
              <Field label="Période (ex. 2022 – 2024)">
                <input value={it.start_date || ""} onChange={(e) => upd({ start_date: e.target.value })} />
              </Field>
              <div className="span-2">
                <Field label="Description">
                  <textarea
                    rows="2"
                    value={it.description}
                    onChange={(e) => upd({ description: e.target.value })}
                  />
                </Field>
              </div>
            </div>
          )}
        />
      </Section>

      <Section title="Formation" hint="Tous les parcours comptent : CEP, FSLC, GCE, CAP, bac, BTS, licence, ingénieur, recyclages et compétences de terrain.">
        <ListEditor
          items={profile.education || []}
          onChange={(v) => set("education", v)}
          addLabel="Ajouter une formation"
          blank={() => ({ degree: "", institution: "", field: "", start_year: "", end_year: "" })}
          render={(it, upd) => (
            <div className="grid-3">
              <Field label="Diplôme / formation">
                <input value={it.degree} onChange={(e) => upd({ degree: e.target.value })} />
              </Field>
              <Field label="Établissement">
                <input value={it.institution} onChange={(e) => upd({ institution: e.target.value })} />
              </Field>
              <Field label="Filière / spécialité">
                <input value={it.field} onChange={(e) => upd({ field: e.target.value })} />
              </Field>
              <Field label="Année de début">
                <input value={it.start_year ?? ""} onChange={(e) => upd({ start_year: e.target.value })} />
              </Field>
              <Field label="Année de fin">
                <input value={it.end_year ?? ""} onChange={(e) => upd({ end_year: e.target.value })} />
              </Field>
            </div>
          )}
        />
      </Section>

      <Section title="Compétences" hint="Ajustez le niveau de maîtrise de chaque compétence détectée ou déclarée." open>
        <ListEditor
          items={profile.skills || []}
          onChange={(v) => set("skills", v)}
          addLabel="Ajouter une compétence"
          blank={() => ({ skill: "", category: "", proficiency: "intermediaire", source: "declared", evidence_count: 0 })}
          render={(it, upd) => (
            <div className="grid-2">
              <Field label="Compétence">
                <input value={it.skill} onChange={(e) => upd({ skill: e.target.value })} />
              </Field>
              <Field label="Niveau">
                <select value={it.proficiency} onChange={(e) => upd({ proficiency: e.target.value })}>
                  {Object.entries(PROFICIENCY_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </Field>
            </div>
          )}
        />
      </Section>

      <div className="grid-2">
        <Section title="Certifications">
          <ListEditor
            items={profile.certifications || []}
            onChange={(v) => set("certifications", v)}
            addLabel="Ajouter une certification"
            blank={() => ({ name: "", issuer: "", year: "" })}
            render={(it, upd) => (
              <div className="grid-2">
                <Field label="Intitulé">
                  <input value={it.name} onChange={(e) => upd({ name: e.target.value })} />
                </Field>
                <Field label="Organisme / année">
                  <input
                    value={it.issuer || ""}
                    placeholder="Organisme"
                    onChange={(e) => upd({ issuer: e.target.value })}
                  />
                  <input
                    className="mt-4"
                    value={it.year ?? ""}
                    placeholder="Année"
                    onChange={(e) => upd({ year: e.target.value })}
                  />
                </Field>
              </div>
            )}
          />
        </Section>

        <Section title="Langues">
          <ListEditor
            items={profile.languages || []}
            onChange={(v) => set("languages", v)}
            addLabel="Ajouter une langue"
            blank={() => ({ language: "", level: "" })}
            render={(it, upd) => (
              <div className="grid-2">
                <Field label="Langue">
                  <input value={it.language} onChange={(e) => upd({ language: e.target.value })} />
                </Field>
                <Field label="Niveau (ex. courant, professionnel)">
                  <input value={it.level} onChange={(e) => upd({ level: e.target.value })} />
                </Field>
              </div>
            )}
          />
        </Section>
      </div>

      <Section
        title="Projets & portfolio"
        hint="Vos réalisations avec liens de preuve (site, dépôt de code, page, photos) : une compétence documentée pèse plus dans le matching."
      >
        <ListEditor
          items={profile.projects || []}
          onChange={(v) => set("projects", v)}
          addLabel="Ajouter un projet / une réalisation"
          blank={() => ({ name: "", description: "", url: "", skills: [] })}
          render={(it, upd) => (
            <div className="grid-2">
              <Field label="Nom du projet / de la réalisation">
                <input value={it.name} onChange={(e) => upd({ name: e.target.value })} />
              </Field>
              <Field label="Lien de preuve (portfolio, GitHub, page…)">
                <input value={it.url || ""} onChange={(e) => upd({ url: e.target.value })} placeholder="https://…" />
              </Field>
              <div className="span-2">
                <Field label="Description">
                  <textarea
                    rows="2"
                    value={it.description}
                    onChange={(e) => upd({ description: e.target.value })}
                  />
                </Field>
              </div>
            </div>
          )}
        />
      </Section>

      <Section title="Préférences professionnelles">
        <div className="grid-2">
          <Field label="Secteurs qui vous intéressent (séparés par des virgules)">
            <textarea
              rows="2"
              value={(prefs.sectors || []).join(", ")}
              onChange={(e) => setPrefs({ sectors: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
            />
          </Field>
          <Field label="Métiers visés (un par ligne)">
            <textarea
              rows="2"
              value={(prefs.target_roles || []).join("\n")}
              onChange={(e) => setPrefs({ target_roles: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean) })}
            />
          </Field>
        </div>
        <div className="inline-fields">
          <span className="field-label">Types de contrat recherchés :</span>
          {CONTRACT_TYPES.map((c) => (
            <label key={c} className="check">
              <input
                type="checkbox"
                checked={(prefs.contract_types || []).includes(c)}
                onChange={(e) =>
                  setPrefs({
                    contract_types: e.target.checked
                      ? [...(prefs.contract_types || []), c]
                      : (prefs.contract_types || []).filter((x) => x !== c),
                  })
                }
              />
              {c}
            </label>
          ))}
          <label className="check">
            <input
              type="checkbox"
              checked={!!prefs.remote_ok}
              onChange={(e) => setPrefs({ remote_ok: e.target.checked })}
            />
            Télétravail accepté
          </label>
        </div>
        <Field label="Lien vers votre profil LinkedIn (l'assistant vous proposera des améliorations)">
          <input
            value={prefs.linkedin_url || ""}
            onChange={(e) => setPrefs({ linkedin_url: e.target.value })}
            placeholder="https://www.linkedin.com/in/votre-profil"
          />
        </Field>
      </Section>
    </div>
  );
}
