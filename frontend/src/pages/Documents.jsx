import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, apiRaw } from "../api/client.js";
import {
  CV_TEMPLATE_LABELS,
  DEFAULT_ACCENT_BY_TEMPLATE,
  LETTER_TEMPLATE_LABELS,
  accentLabel,
  fmtDate,
  mdToHtml,
  plural,
  templateAccentHex,
} from "../lib.js";
import TemplateThumb from "../components/TemplateThumb.jsx";
import AccentRow from "../components/AccentRow.jsx";
import PreviewImage from "../components/PreviewImage.jsx";
import AssistantChat from "../components/AssistantChat.jsx";
import { Icon, I, ArrowIcon } from "../components/icons.jsx";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";

// Page Documents / CV (§35), trois espaces :
//
// 1. ATELIER : uniquement la nouvelle génération. On y crée un CV (ciblé ou
//    généraliste) ou une lettre (ciblée ou généraliste), avec modèle et
//    couleur. Le document généré s'affiche, son PDF part immédiatement en
//    téléchargement, puis « Ranger » nettoie l'atelier.
// 2. HISTORIQUE : tous les documents produits, avec recherche, filtre,
//    aperçu, téléchargement, mise à jour et suppression.
// 3. MODÈLES : le catalogue complet des mises en page CV et lettres, avec
//    un aperçu réel et un accès direct à l'atelier correspondant.
//
// Les modèles ne changent QUE la mise en page : le contenu reste
// exclusivement celui du profil validé (§47).
// L'agent rédacteur d'Ori reste branché en bas de l'atelier.

const DOCS_SUGGESTIONS = [
  "Rédige mon mail de candidature",
  "Mon CV paraît vide, complète-le",
  "Adapte ma lettre à une offre",
  "Quelles offres viser avec mon profil ?",
];

// Partage du CV généraliste : le talent choisit explicitement UN document.
// Les CV ciblés sur une offre restent privés par construction.
function CvSharePanel({
  generalCvs,
  visibility,
  enabled,
  setEnabled,
  choice,
  setChoice,
  onSave,
  onGenerate,
  busy,
  note,
  compact = false,
}) {
  const shared = visibility?.visible;
  return (
    <section className={`dash-card cv-share-card${compact ? " is-compact" : ""}`}>
      <div className="dash-card-head">
        <h2><Icon d={I.shield} size={16} /> CV visible par les recruteurs</h2>
        <span className={`cv-share-status${shared ? " is-on" : ""}`}>
          {shared ? "Partagé" : "Privé"}
        </span>
      </div>
      <p className="cv-share-lead">
        Choisissez un CV généraliste. Seul ce document sera consultable et
        téléchargeable par les recruteurs ; vos CV ciblés et vos autres
        documents restent privés.
      </p>
      {generalCvs.length === 0 ? (
        <div className="cv-share-empty">
          <p>
            Vous n'avez pas encore de CV généraliste. Générez-en un depuis
            l'atelier, puis revenez ici pour le partager.
          </p>
          <button type="button" className="btn btn-outline btn-small" onClick={onGenerate}>
            <Icon d={I.file} size={12} /> Générer un CV généraliste
          </button>
        </div>
      ) : (
        <>
          <label className="check cv-share-toggle">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            Autoriser les recruteurs à voir mon CV généraliste
          </label>
          <label className="field">
            <span>CV généraliste partagé</span>
            <select
              value={choice}
              onChange={(e) => setChoice(e.target.value)}
              disabled={!enabled}
            >
              <option value="">Choisir un CV</option>
              {generalCvs.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.title} · {fmtDate(doc.created_at)}
                </option>
              ))}
            </select>
          </label>
          <div className="actions-row cv-share-actions">
            <button
              type="button"
              className="btn btn-primary btn-small"
              onClick={() => onSave()}
              disabled={busy || (enabled && !choice)}
            >
              {busy ? "Enregistrement…" : "Enregistrer le choix"}
            </button>
            {shared && (
              <button
                type="button"
                className="btn btn-ghost btn-small"
                onClick={() => onSave(false)}
                disabled={busy}
              >
                Retirer le partage
              </button>
            )}
          </div>
          {note && <div className="alert alert-success cv-share-note">{note}</div>}
        </>
      )}
    </section>
  );
}

function docSubtitle(title) {
  const parts = title.split(" · ");
  return parts.slice(1).join(" · ");
}

function kindLabel(doc) {
  if (doc.kind === "cv") return doc.job_id ? "CV ciblé" : "CV généraliste";
  return doc.job_id ? "Lettre ciblée" : "Lettre généraliste";
}

// Pastille de la couleur d'accent du document (couleur du modèle si absente).
function AccentDot({ doc }) {
  const hex = templateAccentHex(doc.template, doc.accent);
  const label = doc.accent
    ? accentLabel(doc.accent)
    : "Couleur du modèle";
  return (
    <span
      className="doc-accent-dot"
      style={{ background: hex || "#9AA5A0" }}
      title={`Accent : ${label}`}
    />
  );
}

// Sélecteur de modèle d'un atelier : pastilles + aperçu réel + couleur.
function ModelPicker({
  kind,
  templates,
  selectedId,
  onSelect,
  accent,
  onAccent,
  onGenerate,
  busy,
  generateLabel,
}) {
  const template = templates.find((t) => t.id === selectedId) || templates[0];
  if (!template) return null;
  const src = kind === "cv"
    ? `/templates/cv-${template.id}.png`
    : `/templates/lettre-${template.id}.png`;
  return (
    <div className="gen-picker">
      <label className="field gen-model-field">
        <span>{kind === "cv" ? "Modèle de CV" : "Modèle de lettre"}</span>
        <select value={template.id} onChange={(e) => onSelect(e.target.value)}>
          {templates.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}{t.ats_friendly ? " · ATS" : ""}
            </option>
          ))}
        </select>
      </label>
      <div className="gen-preview">
        <PreviewImage
          src={src}
          alt={`Aperçu du modèle ${template.name}, rendu PDF réel sur des données d'exemple`}
          className="gen-preview-img"
          loading="eager"
          fallback={
            <TemplateThumb
              template={{
                id: kind === "cv" ? template.id : (template.id === "email" ? "" : "classique"),
                columns: template.columns || 1,
              }}
              accent={accent}
              flat={kind === "lettre" && template.id === "email"}
            />
          }
        />
        <div className="gen-preview-copy">
          <div className="tpl-card-head">
            <h3>{template.name}</h3>
            {template.ats_friendly && (
              <span className="badge badge-strong">Compatible ATS</span>
            )}
          </div>
          <p className="small muted">{template.description}</p>
          <AccentRow accent={accent} onPick={onAccent} />
          <p className="docs-accent-note">
            La couleur s'applique au PDF généré. Le modèle ATS suit aussi la
            couleur choisie ; sans choix, il garde sa charte par défaut.
          </p>
          <button
            type="button"
            className="btn btn-primary btn-small"
            onClick={() => onGenerate(template.id)}
            disabled={!!busy}
          >
            {busy ? "Génération…" : generateLabel}
            {!busy && <ArrowIcon direction="right" size={12} />}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Documents() {
  const [docs, setDocs] = useState(null);
  const [cvTemplates, setCvTemplates] = useState([]);
  const [letterTemplates, setLetterTemplates] = useState([]);
  const [selected, setSelected] = useState(null);   // historique
  const [current, setCurrent] = useState(null);     // atelier (document du moment)
  const [vue, setVue] = useState("atelier");        // atelier | historique | modeles
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [templateFilter, setTemplateFilter] = useState("all");
  const [error, setError] = useState("");
  const [downloadError, setDownloadError] = useState("");
  const [cvOpen, setCvOpen] = useState(false);
  const [letterOpen, setLetterOpen] = useState(false);
  const [cvSelection, setCvSelection] = useState("");
  const [letterSelection, setLetterSelection] = useState("");
  const [accent, setAccent] = useState("");
  const [letterAccent, setLetterAccent] = useState("");
  const [busy, setBusy] = useState("");
  const [readyNote, setReadyNote] = useState("");
  const [previewOpen, setPreviewOpen] = useState(false);
  // Mise à jour d'un document : panneau avec modèle + couleur.
  const [updateDoc, setUpdateDoc] = useState(null);
  const [updateTemplate, setUpdateTemplate] = useState("");
  const [updateAccent, setUpdateAccent] = useState("");
  const [updateBusy, setUpdateBusy] = useState(false);
  // Partage du CV généraliste avec les recruteurs.
  const [cvVisibility, setCvVisibility] = useState(null);
  const [cvShareEnabled, setCvShareEnabled] = useState(false);
  const [cvShareChoice, setCvShareChoice] = useState("");
  const [cvShareBusy, setCvShareBusy] = useState(false);
  const [cvShareNote, setCvShareNote] = useState("");
  const [searchParams, setSearchParams] = useSearchParams();
  const workspaceRef = useRef(null);
  const cvRef = useRef(null);
  const letterRef = useRef(null);
  const shareRef = useRef(null);
  const lastOpenRef = useRef(null);

  // Chargement initial (une seule fois).
  useEffect(() => {
    api("/documents")
      .then((list) => {
        setDocs(list);
        setSelected(list[0] || null);
      })
      .catch((e) => setError(e.detail));
    api("/cv-templates")
      .then((list) => {
        setCvTemplates(list);
        setCvSelection(list[0]?.id || "");
      })
      .catch(() => {});
    api("/letter-templates")
      .then((list) => {
        setLetterTemplates(list);
        setLetterSelection(list[0]?.id || "");
      })
      .catch(() => {});
    api("/profile/cv-visibility")
      .then((visibility) => {
        setCvVisibility(visibility);
        setCvShareEnabled(!!visibility.visible);
        setCvShareChoice(
          visibility.document_id ? String(visibility.document_id) : "",
        );
      })
      .catch(() => {});
  }, []);

  // Synchronise l'onglet avec l'URL (liens profonds et bouton Retour).
  useEffect(() => {
    const requested = searchParams.get("vue");
    setVue(
      requested === "historique" || requested === "modeles"
        ? requested
        : "atelier",
    );
  }, [searchParams]);

  // Arrivée depuis une génération : /documents?open=ID montre le document
  // dans l'atelier. /documents?lettre=1 ouvre la lettre généraliste.
  useEffect(() => {
    if (!docs) return;
    const openId = Number(searchParams.get("open")) || null;
    const historyMode = searchParams.get("vue") === "historique";
    // Retour à une URL sans « open » (Ranger, fermeture) : on oublie le
    // dernier document ouvert pour qu'un nouveau lien ?open=ID fonctionne.
    if (!openId) lastOpenRef.current = null;
    if (openId && lastOpenRef.current !== openId) {
      const found = docs.find((d) => d.id === openId);
      if (found) {
        lastOpenRef.current = openId;
        setSelected(found);
        if (!historyMode) {
          setCurrent(found);
          setReadyNote("Votre document est prêt. Le PDF part aussi dans vos téléchargements.");
          window.setTimeout(() => {
            workspaceRef.current?.scrollIntoView({ block: "start" });
          }, 80);
        }
      }
    }
    if (searchParams.get("lettre")) {
      setLetterOpen(true);
      setVue("atelier");
      window.setTimeout(() => {
        letterRef.current?.scrollIntoView({ block: "start" });
      }, 120);
    }
  }, [docs, searchParams]);

  // En historique, la sélection suit toujours la liste filtrée.
  const filtered = useMemo(() => {
    if (!docs) return [];
    const needle = query.trim().toLowerCase();
    return docs.filter((d) => {
      if (filter !== "all" && d.kind !== filter) return false;
      if (!needle) return true;
      const name = d.kind === "cv"
        ? (cvTemplates.find((t) => t.id === d.template)?.name
          || CV_TEMPLATE_LABELS[d.template] || d.template)
        : (letterTemplates.find((t) => t.id === d.template)?.name
          || LETTER_TEMPLATE_LABELS[d.template] || d.template);
      return `${d.title} ${name}`.toLowerCase().includes(needle);
    });
  }, [docs, filter, query, cvTemplates, letterTemplates]);

  useEffect(() => {
    if (vue !== "historique") return;
    if (filtered.length === 0) {
      setSelected(null);
      return;
    }
    if (!selected || !filtered.some((d) => d.id === selected.id)) {
      setSelected(filtered[0]);
    }
  }, [vue, filtered, selected]);

  async function refreshDocs() {
    const list = await api("/documents");
    setDocs(list);
    return list;
  }

  async function download(doc, format) {
    setDownloadError("");
    try {
      const res = await apiRaw(`/documents/${doc.id}/export?format=${format}`);
      if (!res.ok) throw new Error("Téléchargement impossible");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const ext = format === "pdf" ? "pdf" : "md";
      a.download = `${doc.kind === "cv" ? "CV" : "Lettre"}-${doc.id}.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setDownloadError(err.message || "Téléchargement impossible");
    }
  }

  function scrollToWorkspace() {
    window.setTimeout(() => {
      workspaceRef.current?.scrollIntoView({ block: "start" });
    }, 80);
  }

  function switchTab(next) {
    setVue(next);
    setUpdateDoc(null);
    const params = new URLSearchParams(searchParams);
    if (next === "historique" || next === "modeles") params.set("vue", next);
    else params.delete("vue");
    setSearchParams(params, { replace: true });
  }

  // Depuis la galerie : on ouvre l'atelier concerné avec le modèle choisi,
  // puis on amène l'utilisateur sur le sélecteur pour ajuster la couleur.
  function chooseTemplate(kind, templateId) {
    if (kind === "cv") {
      setCvSelection(templateId);
      setCvOpen(true);
      setLetterOpen(false);
      setVue("atelier");
      window.setTimeout(() => {
        cvRef.current?.scrollIntoView({ block: "start" });
      }, 100);
    } else {
      setLetterSelection(templateId);
      setLetterOpen(true);
      setCvOpen(false);
      setVue("atelier");
      window.setTimeout(() => {
        letterRef.current?.scrollIntoView({ block: "start" });
      }, 100);
    }
    const params = new URLSearchParams(searchParams);
    params.delete("vue");
    if (kind === "cv") params.delete("lettre");
    setSearchParams(params, { replace: true });
  }

  // Le lien profond ?lettre=1 ne doit pas rouvrir l'atelier lettre une fois
  // celui-ci refermé : on nettoie le paramètre au passage.
  function clearLetterParam() {
    if (!searchParams.get("lettre")) return;
    const params = new URLSearchParams(searchParams);
    params.delete("lettre");
    setSearchParams(params, { replace: true });
  }

  function toggleLetter() {
    const next = !letterOpen;
    setLetterOpen(next);
    if (!next) clearLetterParam();
  }

  // CV GÉNÉRALISTE : profil complet, sans offre ciblée (§47 respecté).
  async function generateGeneral(templateId) {
    setBusy("general");
    setDownloadError("");
    try {
      const doc = await api("/cv", {
        method: "POST",
        body: { template: templateId, accent: accent || null },
      });
      const list = await refreshDocs();
      const fresh = list.find((d) => d.id === doc.id) || doc;
      setCurrent(fresh);
      setSelected(fresh);
      setCvOpen(false);
      setPreviewOpen(false);
      setUpdateDoc(null);
      setReadyNote("Votre CV généraliste est prêt. Le PDF part aussi dans vos téléchargements.");
      download(doc, "pdf");
      scrollToWorkspace();
    } catch (err) {
      setDownloadError(err.detail);
    } finally {
      setBusy("");
    }
  }

  // LETTRE GÉNÉRALISTE : sans offre, destinataire à compléter
  // ([Nom de l'entreprise], [Ville]) : aucune coordonnée inventée.
  async function generateLetterGeneral(templateId) {
    setBusy("letter-general");
    setDownloadError("");
    try {
      const doc = await api("/letter", {
        method: "POST",
        body: { template: templateId, accent: letterAccent || null },
      });
      const list = await refreshDocs();
      const fresh = list.find((d) => d.id === doc.id) || doc;
      setCurrent(fresh);
      setSelected(fresh);
      setLetterOpen(false);
      clearLetterParam();
      setPreviewOpen(false);
      setUpdateDoc(null);
      setReadyNote("Votre lettre généraliste est prête. Le PDF part aussi dans vos téléchargements.");
      download(doc, "pdf");
      scrollToWorkspace();
    } catch (err) {
      setDownloadError(err.detail);
    } finally {
      setBusy("");
    }
  }

  // Mise à jour : le document est RÉGÉNÉRÉ depuis le profil validé au
  // moment de l'action : même offre s'il est ciblé, modèle et couleur au
  // choix. Rien n'est inventé : seuls les faits actuels sont repris.
  function openUpdate(doc) {
    setSelected(doc);
    setUpdateDoc(doc);
    setUpdateTemplate(doc.template || "");
    setUpdateAccent(doc.accent || "");
    setReadyNote("");
  }

  async function saveUpdate() {
    if (!updateDoc) return;
    setUpdateBusy(true);
    setDownloadError("");
    try {
      const updated = await api(`/documents/${updateDoc.id}/refresh`, {
        method: "POST",
        body: { template: updateTemplate || undefined, accent: updateAccent || null },
      });
      setDocs((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
      if (current?.id === updated.id) setCurrent(updated);
      setSelected(updated);
      setUpdateDoc(updated);
      setReadyNote("Document mis à jour depuis votre profil actuel. Le nouveau PDF part dans vos téléchargements.");
      download(updated, "pdf");
    } catch (err) {
      setDownloadError(err.detail);
    } finally {
      setUpdateBusy(false);
    }
  }

  async function removeDoc(doc) {
    const confirmed = window.confirm(
      `Supprimer « ${doc.title} » ? Cette action est définitive.`,
    );
    if (!confirmed) return;
    setDownloadError("");
    try {
      await api(`/documents/${doc.id}`, { method: "DELETE" });
      const list = await refreshDocs();
      if (current?.id === doc.id) {
        setCurrent(null);
        setReadyNote("");
      }
      if (selected?.id === doc.id) setSelected(list[0] || null);
      if (updateDoc?.id === doc.id) setUpdateDoc(null);
      if (cvVisibility?.document_id === doc.id) {
        setCvVisibility({ visible: false, document_id: null, document: null });
        setCvShareEnabled(false);
        setCvShareChoice("");
        setCvShareNote("Le CV partagé a été supprimé : le partage est désactivé.");
      }
    } catch (err) {
      setDownloadError(err.detail);
    }
  }

  // « Ranger » : l'atelier se nettoie, le document reste dans l'historique.
  function storeCurrent() {
    setCurrent(null);
    setReadyNote("");
    setPreviewOpen(false);
    setUpdateDoc(null);
    const params = new URLSearchParams(searchParams);
    params.delete("open");
    setSearchParams(params, { replace: true });
  }

  if (error && !docs) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!docs) {
    return <div className="page"><Loader /></div>;
  }

  const cvCount = docs.filter((d) => d.kind === "cv").length;
  const letterCount = docs.filter((d) => d.kind === "cover_letter").length;
  const targetedCount = docs.filter((d) => d.job_id).length;
  const generalCvs = docs.filter((d) => d.kind === "cv" && !d.job_id);
  const sharedCvId = cvVisibility?.visible ? cvVisibility.document_id : null;

  async function updateCvShare(visible, documentId = null) {
    if (visible && !documentId) {
      setDownloadError("Choisissez un CV généraliste à partager.");
      return;
    }
    setCvShareBusy(true);
    setDownloadError("");
    setCvShareNote("");
    try {
      const visibility = await api("/profile/cv-visibility", {
        method: "PUT",
        body: {
          visible: !!visible,
          document_id: visible ? Number(documentId) : null,
        },
      });
      setCvVisibility(visibility);
      setCvShareEnabled(!!visibility.visible);
      setCvShareChoice(
        visibility.document_id ? String(visibility.document_id) : "",
      );
      setCvShareNote(
        visibility.visible
          ? "Votre CV généraliste est maintenant visible par les recruteurs."
          : "Le partage du CV est désactivé.",
      );
      return visibility;
    } catch (err) {
      setDownloadError(err.detail);
      return null;
    } finally {
      setCvShareBusy(false);
    }
  }

  function saveCvShare(forceVisible = null) {
    const visible = forceVisible === null ? cvShareEnabled : forceVisible;
    return updateCvShare(visible, cvShareChoice);
  }

  function shareDocument(doc) {
    if (!doc || doc.kind !== "cv" || doc.job_id) return;
    setCvShareEnabled(true);
    setCvShareChoice(String(doc.id));
    return updateCvShare(true, doc.id);
  }

  function openSharePanel() {
    switchTab("atelier");
    window.setTimeout(() => {
      shareRef.current?.scrollIntoView({ block: "start" });
    }, 100);
  }

  function openGeneralCv() {
    switchTab("atelier");
    setCvOpen(true);
    window.setTimeout(() => {
      cvRef.current?.scrollIntoView({ block: "start" });
    }, 100);
  }

  const nameOf = (doc) => {
    if (doc.kind === "cv") {
      return cvTemplates.find((t) => t.id === doc.template)?.name
        || CV_TEMPLATE_LABELS[doc.template]
        || doc.template;
    }
    return letterTemplates.find((t) => t.id === doc.template)?.name
      || LETTER_TEMPLATE_LABELS[doc.template]
      || doc.template;
  };

  const updateModels = updateDoc?.kind === "cv" ? cvTemplates : letterTemplates;

  const templateItems = [
    ...cvTemplates.map((t) => ({ ...t, kind: "cv" })),
    ...letterTemplates.map((t) => ({ ...t, kind: "lettre" })),
  ];
  const filteredTemplates = templateFilter === "all"
    ? templateItems
    : templateItems.filter((t) => t.kind === templateFilter);
  const cvTemplateCount = templateItems.filter((t) => t.kind === "cv").length;
  const letterTemplateCount = templateItems.filter((t) => t.kind === "lettre").length;

  function updatePanelFor(doc) {
    if (!updateDoc || updateDoc.id !== doc.id) return null;
    const tmpl = updateModels.find((t) => t.id === updateTemplate)
      || updateModels.find((t) => t.id === doc.template)
      || updateModels[0]
      || { id: doc.template || "", name: "Modèle actuel", columns: 1 };
    const previewSrc = doc.kind === "cv"
      ? `/templates/cv-${tmpl.id}.png`
      : `/templates/lettre-${tmpl.id}.png`;
    const accentValue = updateAccent
      || DEFAULT_ACCENT_BY_TEMPLATE[tmpl.id]
      || "";
    const accentText = updateAccent
      ? accentLabel(updateAccent)
      : (tmpl.id === "ats"
        ? "Turquoise (couleur du modèle)"
        : (accentLabel(accentValue) || "Couleur du modèle"));
    const accentColor = templateAccentHex(tmpl.id, updateAccent)
      || "#C9D3CD";
    return (
      <div className="doc-update">
        <div className="docs-general-head">
          <strong>Mettre à jour ce document</strong>
          <button
            type="button"
            className="btn btn-ghost btn-small"
            onClick={() => setUpdateDoc(null)}
          >
            Fermer
          </button>
        </div>
        <p className="small muted" style={{ marginTop: 0 }}>
          Le document est régénéré depuis votre profil validé au moment de la
          mise à jour
          {doc.job_id ? ", toujours pour la même offre" : ""}. Le contenu
          reste celui du profil (§47).
        </p>
        <div className="doc-update-body">
          <div className="doc-update-preview-wrap">
            <PreviewImage
              src={previewSrc}
              alt={`Aperçu du modèle ${tmpl.name}, rendu PDF réel sur des données d'exemple`}
              className="doc-update-preview"
              loading="eager"
              fallback={
                <TemplateThumb
                  template={{
                    id: doc.kind === "cv"
                      ? tmpl.id
                      : (tmpl.id === "email" ? "" : "classique"),
                    columns: tmpl.columns || 1,
                  }}
                  accent={updateAccent}
                  flat={doc.kind === "lettre" && tmpl.id === "email"}
                />
              }
            />
            <span className="doc-update-accent">
              <span className="doc-accent-swatch" style={{ background: accentColor }} />
              <span className="small muted">{accentText}</span>
            </span>
          </div>
          <div className="doc-update-controls">
            <label className="field">
              <span>Modèle</span>
              <select
                value={tmpl.id}
                onChange={(e) => setUpdateTemplate(e.target.value)}
              >
                {!updateModels.some((t) => t.id === tmpl.id) && (
                  <option value={tmpl.id}>{tmpl.name}</option>
                )}
                {updateModels.map((t) => (
                  <option key={`upd-${t.id}`} value={t.id}>
                    {t.name}{t.ats_friendly ? " · ATS" : ""}
                  </option>
                ))}
              </select>
            </label>
            <AccentRow accent={updateAccent} onPick={setUpdateAccent} />
            <p className="docs-accent-note">
              La couleur s'applique au PDF régénéré et à l'aperçu du modèle.
              Le modèle ATS suit aussi la couleur choisie.
            </p>
            <div className="actions-row" style={{ marginTop: "0.6rem" }}>
              <button
                type="button"
                className="btn btn-primary btn-small"
                onClick={saveUpdate}
                disabled={updateBusy}
              >
                {updateBusy ? "Mise à jour…" : "Mettre à jour"}
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-small"
                onClick={() => setUpdateDoc(null)}
              >
                Annuler
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page docs-page">
      {/* ---------- Bandeau ---------- */}
      <section className="home-hero docs-hero">
        <span className="docs-eyebrow">CV Intelligence</span>
        <h1>Documents</h1>
        <p className="docs-hero-lead">
          L'atelier pour créer, les modèles pour choisir, l'historique pour
          retrouver, télécharger et mettre à jour.
        </p>
        <p className="docs-hero-note">
          Générez un CV ou une lettre, avec une offre ou sans, puis rangez-le.
          L'atelier ne garde que le document du moment, les modèles restent
          consultables et tout le reste vit dans l'historique. Le contenu vient
          exclusivement de votre profil validé (§47).
        </p>
      </section>

      {/* ---------- Onglets Atelier / Historique / Modèles ---------- */}
      <div className="docs-tabs" role="tablist" aria-label="Espace documents">
        <button
          type="button"
          role="tab"
          aria-selected={vue === "atelier"}
          className={`docs-tab${vue === "atelier" ? " is-active" : ""}`}
          onClick={() => switchTab("atelier")}
        >
          <Icon d={I.spark} size={15} />
          <span>Atelier</span>
          {current && <span className="docs-tab-count">1</span>}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={vue === "historique"}
          className={`docs-tab${vue === "historique" ? " is-active" : ""}`}
          onClick={() => switchTab("historique")}
        >
          <Icon d={I.folder} size={15} />
          <span>Historique</span>
          <span className="docs-tab-count">{docs.length}</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={vue === "modeles"}
          className={`docs-tab${vue === "modeles" ? " is-active" : ""}`}
          onClick={() => switchTab("modeles")}
        >
          <Icon d={I.layers} size={15} />
          <span>Modèles</span>
          <span className="docs-tab-count">
            {cvTemplates.length + letterTemplates.length}
          </span>
        </button>
      </div>

      <ErrorNote error={error} />
      <ErrorNote error={downloadError} />

      {/* ================================================================
          ATELIER : uniquement la nouvelle génération
          ================================================================ */}
      {vue === "atelier" && (
        <div className="dash-columns">
          <div className="dash-col-main">
            {/* Document du moment */}
            {current && (
              <section className="docs-current" ref={workspaceRef}>
                <div className="docs-current-head">
                  <div className="docs-current-id">
                    <span className="docs-current-icon"><Icon d={I.file} size={19} /></span>
                    <div>
                      <span className="docs-current-eyebrow">Espace de génération</span>
                      <h2>{kindLabel(current)} · {nameOf(current)}</h2>
                      <p className="small muted">
                        {docSubtitle(current.title) || current.title}
                        {" · "}{fmtDate(current.created_at)}
                        {current.job_id && (
                          <> · <Link to={`/opportunites/${current.job_id}`}>offre liée</Link></>
                        )}
                      </p>
                    </div>
                  </div>
                  <span className="docs-current-badge">
                    <Icon d={I.check} size={12} /> Prêt
                  </span>
                </div>

                {readyNote && (
                  <div className="docs-ready">
                    <Icon d={I.check} size={16} />
                    <div><strong>{readyNote}</strong></div>
                    <button
                      type="button"
                      className="btn btn-primary btn-small"
                      onClick={() => download(current, "pdf")}
                    >
                      Télécharger le PDF
                    </button>
                  </div>
                )}

                <div className="docs-current-actions">
                  <button
                    className="btn btn-primary btn-small"
                    onClick={() => download(current, "pdf")}
                  >
                    Télécharger le PDF (A4)
                  </button>
                  <button
                    className="btn btn-ghost btn-small"
                    onClick={() => download(current, "md")}
                  >
                    Markdown
                  </button>
                  <button
                    className="btn btn-outline btn-small"
                    onClick={() => openUpdate(current)}
                  >
                    <Icon d={I.pen} size={12} /> Mettre à jour
                  </button>
                  <button
                    className="btn btn-ghost btn-small"
                    onClick={() => setPreviewOpen((v) => !v)}
                  >
                    {previewOpen ? "Masquer le contenu" : "Lire le contenu"}
                  </button>
                  <button
                    className="btn btn-outline btn-small docs-store"
                    onClick={storeCurrent}
                  >
                    <Icon d={I.folder} size={12} /> Ranger dans l'historique
                  </button>
                  <button
                    className="btn btn-ghost btn-small doc-danger"
                    onClick={() => removeDoc(current)}
                  >
                    Supprimer
                  </button>
                </div>

                <p className="docs-current-note">
                  Une fois relu et téléchargé, rangez-le : l'atelier redevient
                  vide pour le prochain document. Il reste intact dans
                  l'historique.
                </p>

                {previewOpen && (
                  <div
                    className="doc-content"
                    dangerouslySetInnerHTML={{ __html: mdToHtml(current.content_markdown) }}
                  />
                )}
                {updatePanelFor(current)}
              </section>
            )}

            {/* Génération */}
            {!current && docs.length > 0 && (
              <div className="docs-clean-note">
                <Icon d={I.folder} size={16} />
                <span>
                  L'atelier est vide. Vos {docs.length} document{plural(docs.length, "", "s")}{" "}
                  sont conservés dans l'historique.
                </span>
                <button
                  type="button"
                  className="btn btn-ghost btn-small"
                  onClick={() => switchTab("historique")}
                >
                  Ouvrir l'historique <ArrowIcon direction="right" size={11} />
                </button>
              </div>
            )}

            <div className="gen-grid">
              {/* CV */}
              <section className="gen-card" ref={cvRef}>
                <div className="gen-card-head">
                  <span className="gen-icon gen-icon-cv"><Icon d={I.file} size={20} /></span>
                  <div>
                    <span className="gen-eyebrow">Atelier 1</span>
                    <h2>CV</h2>
                    <p>
                      Ciblé sur une offre précise, ou généraliste pour tout
                      votre parcours.
                    </p>
                  </div>
                </div>
                <div className="gen-card-actions">
                  <Link className="btn btn-primary btn-small" to="/opportunites?choisir=cv">
                    Choisir une offre <ArrowIcon direction="right" size={11} />
                  </Link>
                  <button
                    type="button"
                    className="btn btn-outline btn-small"
                    onClick={() => setCvOpen((v) => !v)}
                  >
                    {cvOpen ? "Fermer" : "CV généraliste"}
                  </button>
                </div>
                {cvOpen && (
                  <ModelPicker
                    kind="cv"
                    templates={cvTemplates}
                    selectedId={cvSelection}
                    onSelect={setCvSelection}
                    accent={accent}
                    onAccent={setAccent}
                    onGenerate={generateGeneral}
                    busy={busy === "general" ? busy : ""}
                    generateLabel="Générer mon CV généraliste"
                  />
                )}
              </section>

              {/* Lettre */}
              <section className="gen-card" ref={letterRef}>
                <div className="gen-card-head">
                  <span className="gen-icon gen-icon-letter"><Icon d={I.mail} size={20} /></span>
                  <div>
                    <span className="gen-eyebrow">Atelier 2</span>
                    <h2>Lettre de motivation</h2>
                    <p>
                      Trois écritures, ciblées par une offre ou généralistes.
                    </p>
                  </div>
                </div>
                <div className="gen-card-actions">
                  <Link className="btn btn-primary btn-small" to="/opportunites?choisir=lettre">
                    Choisir une offre <ArrowIcon direction="right" size={11} />
                  </Link>
                  <button
                    type="button"
                    className="btn btn-outline btn-small"
                    onClick={toggleLetter}
                  >
                    {letterOpen ? "Fermer" : "Lettre généraliste"}
                  </button>
                </div>
                {letterOpen && (
                  <>
                    <p className="small muted gen-note">
                      Sans offre ciblée, le destinataire reste «&nbsp;[Nom de
                      l'entreprise]&nbsp;» et «&nbsp;[Ville]&nbsp;», à compléter
                      vous-même, aucune coordonnée inventée (§47).
                    </p>
                    <ModelPicker
                      kind="lettre"
                      templates={letterTemplates}
                      selectedId={letterSelection}
                      onSelect={setLetterSelection}
                      accent={letterAccent}
                      onAccent={setLetterAccent}
                      onGenerate={generateLetterGeneral}
                      busy={busy === "letter-general" ? busy : ""}
                      generateLabel="Générer ma lettre généraliste"
                    />
                  </>
                )}
              </section>
            </div>

            {/* Agent rédacteur */}
            <AssistantChat compact suggestions={DOCS_SUGGESTIONS} pageContext="Documents" />
          </div>

          {/* Colonne latérale de l'atelier */}
          <div className="dash-col-side">
            <div ref={shareRef}>
              <CvSharePanel
                generalCvs={generalCvs}
                visibility={cvVisibility}
                enabled={cvShareEnabled}
                setEnabled={setCvShareEnabled}
                choice={cvShareChoice}
                setChoice={setCvShareChoice}
                onSave={saveCvShare}
                onGenerate={openGeneralCv}
                busy={cvShareBusy}
                note={cvShareNote}
                compact
              />
            </div>

            <section className="dash-card">
              <div className="dash-card-head">
                <h2><Icon d={I.spark} size={16} /> Votre agent rédacteur</h2>
              </div>
              <ul className="docs-guide">
                <li>
                  <strong>Un CV qui paraît vide ?</strong>
                  <p>
                    Ori repère les sections manquantes et propose des faits
                    vrais à ajouter, y compris les expériences informelles
                    (§5bis).
                  </p>
                </li>
                <li>
                  <strong>Une lettre qui sort de l'ordinaire</strong>
                  <p>
                    Rédigée depuis vos preuves : demandez-la dans la barre
                    d'en bas.
                  </p>
                </li>
                <li>
                  <strong>Le mail d'accompagnement</strong>
                  <p>
                    Objet, corps, formule : « Rédige mon mail de candidature ».
                  </p>
                </li>
              </ul>
            </section>

            <section className="dash-card">
              <div className="dash-card-head">
                <h2><Icon d={I.compass} size={16} /> Quel modèle choisir ?</h2>
              </div>
              <ul className="docs-guide">
                <li>
                  <strong>Candidature en ligne, grande entreprise</strong>
                  <p>« ATS » : les robots de tri lisent tout, sans fioritures.</p>
                </li>
                <li>
                  <strong>Beaucoup de compétences à montrer</strong>
                  <p>« Deux colonnes » : elles se voient en un coup d'œil.</p>
                </li>
                <li>
                  <strong>Administration, banque, éducation</strong>
                  <p>« Élégant » : serif et conventions classiques.</p>
                </li>
                <li>
                  <strong>Début de parcours, sélection rapide</strong>
                  <p>« Compact » : tout sur une page.</p>
                </li>
              </ul>
            </section>

            <section className="dash-card">
              <div className="dash-card-head">
                <h2><Icon d={I.clipboard} size={16} /> Après la génération</h2>
              </div>
              <ol className="learn-howto-steps">
                <li>
                  <span className="learn-howto-num">1</span>
                  <div>
                    <strong>Relire</strong>
                    <p>Le contenu vient de votre profil : corrigez-y toute imprécision.</p>
                  </div>
                </li>
                <li>
                  <span className="learn-howto-num">2</span>
                  <div>
                    <strong>Ranger</strong>
                    <p>L'atelier se nettoie ; le document rejoint l'historique.</p>
                  </div>
                </li>
                <li>
                  <span className="learn-howto-num">3</span>
                  <div>
                    <strong>Postuler</strong>
                    <p>
                      Depuis <Link to="/opportunites">l'offre</Link> ou{" "}
                      <Link to="/candidatures">votre suivi</Link>.
                    </p>
                  </div>
                </li>
              </ol>
            </section>
          </div>
        </div>
      )}

      {/* ================================================================
          MODÈLES : catalogue complet des mises en page
          ================================================================ */}
      {vue === "modeles" && (
        <section className="templates-shell">
          <div className="templates-head">
            <div>
              <span className="docs-eyebrow">Bibliothèque de modèles</span>
              <h2>Toutes les mises en page disponibles</h2>
              <p className="small muted">
                Choisissez un modèle pour l'ouvrir directement dans l'atelier.
                Vous pourrez y régler la couleur et générer le document depuis
                votre profil validé. Le modèle ne change que la présentation :
                aucun contenu n'est inventé (§47).
              </p>
            </div>
            <div className="doc-filters docs-filters" role="group" aria-label="Filtrer les modèles">
              <button
                type="button"
                className={`doc-filter ${templateFilter === "all" ? "active" : ""}`}
                onClick={() => setTemplateFilter("all")}
              >
                Tous ({templateItems.length})
              </button>
              <button
                type="button"
                className={`doc-filter ${templateFilter === "cv" ? "active" : ""}`}
                onClick={() => setTemplateFilter("cv")}
              >
                CV ({cvTemplateCount})
              </button>
              <button
                type="button"
                className={`doc-filter ${templateFilter === "lettre" ? "active" : ""}`}
                onClick={() => setTemplateFilter("lettre")}
              >
                Lettres ({letterTemplateCount})
              </button>
            </div>
          </div>

          {filteredTemplates.length === 0 ? (
            <Empty title="Aucun modèle à afficher">
              <p>Le catalogue de modèles est en cours de chargement.</p>
            </Empty>
          ) : (
            <div className="template-gallery">
              {filteredTemplates.map((t) => {
                const isCv = t.kind === "cv";
                const defaultAccent = isCv
                  ? DEFAULT_ACCENT_BY_TEMPLATE[t.id]
                  : null;
                const defaultAccentLabel = accentLabel(defaultAccent);
                const accentText = !isCv
                  ? "Couleur réglable dans l'atelier"
                  : (t.id === "ats"
                    ? "Turquoise par défaut, personnalisable"
                    : (defaultAccentLabel
                      ? `Accent ${defaultAccentLabel.toLowerCase()}`
                      : "Couleur réglable dans l'atelier"));
                const swatch = !isCv
                  ? "#C9D3CD"
                  : (templateAccentHex(t.id) || "#C9D3CD");
                return (
                  <article className="template-card" key={`${t.kind}-${t.id}`}>
                    <div className="template-card-visual">
                      <PreviewImage
                        src={isCv
                          ? `/templates/cv-${t.id}.png`
                          : `/templates/lettre-${t.id}.png`}
                        alt={`Aperçu du modèle ${t.name}, rendu PDF réel sur des données d'exemple`}
                        className="template-card-img"
                        loading="lazy"
                        fallback={
                          <TemplateThumb
                            template={{
                              id: isCv ? t.id : (t.id === "email" ? "" : "classique"),
                              columns: t.columns || 1,
                            }}
                            flat={!isCv && t.id === "email"}
                          />
                        }
                      />
                      <span className="template-card-type">
                        {isCv ? "CV" : "Lettre"}
                      </span>
                      {isCv && t.ats_friendly && (
                        <span className="template-card-ats">Compatible ATS</span>
                      )}
                    </div>
                    <div className="template-card-body">
                      <div className="template-card-head">
                        <h3>{t.name}</h3>
                        <span
                          className="template-swatch"
                          style={{ background: swatch }}
                          aria-hidden="true"
                        />
                      </div>
                      <p>{t.description}</p>
                      <div className="template-card-meta">
                        <span>
                          {isCv
                            ? (t.columns === 2 ? "Deux colonnes" : "Une colonne")
                            : "Format lettre"}
                        </span>
                        <span>{accentText}</span>
                      </div>
                      <button
                        type="button"
                        className="btn btn-primary btn-small"
                        onClick={() => chooseTemplate(t.kind, t.id)}
                      >
                        Utiliser ce modèle <ArrowIcon direction="right" size={11} />
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}

          <div className="templates-note">
            <Icon d={I.shield} size={16} />
            <p>
              Les modèles ATS restent volontairement sobres et sans couleur
              vive. Pour une candidature en ligne, privilégiez-les : les robots
              de tri lisent mieux une structure simple.
            </p>
          </div>
        </section>
      )}

      {/* ================================================================
          HISTORIQUE : tous les documents, avec actions
          ================================================================ */}
      {vue === "historique" && (
        <div className="docs-history-stack">
          <div className="opps-stats docs-stats">
            <div className="opps-stat opps-stat-green">
              <span className="opps-stat-icon"><Icon d={I.folder} size={18} /></span>
              <span className="opps-stat-num">{docs.length}</span>
              <span className="opps-stat-label">
                document{plural(docs.length, "", "s")} conservé{plural(docs.length, "", "s")}
              </span>
              <span className="opps-stat-note">téléchargeables et supprimables</span>
            </div>
            <div className="opps-stat opps-stat-violet">
              <span className="opps-stat-icon"><Icon d={I.file} size={18} /></span>
              <span className="opps-stat-num">{cvCount}</span>
              <span className="opps-stat-label">CV</span>
              <span className="opps-stat-note">ciblés par une offre ou généralistes</span>
            </div>
            <div className="opps-stat opps-stat-blue">
              <span className="opps-stat-icon"><Icon d={I.mail} size={18} /></span>
              <span className="opps-stat-num">{letterCount}</span>
              <span className="opps-stat-label">lettre{plural(letterCount, "", "s")}</span>
              <span className="opps-stat-note">écrites depuis votre profil validé</span>
            </div>
            <div className="opps-stat opps-stat-orange">
              <span className="opps-stat-icon"><Icon d={I.target} size={18} /></span>
              <span className="opps-stat-num">{targetedCount}</span>
              <span className="opps-stat-label">document{plural(targetedCount, "", "s")} ciblé{plural(targetedCount, "", "s")}</span>
              <span className="opps-stat-note">rattachés à une offre précise</span>
            </div>
          </div>

          <CvSharePanel
            generalCvs={generalCvs}
            visibility={cvVisibility}
            enabled={cvShareEnabled}
            setEnabled={setCvShareEnabled}
            choice={cvShareChoice}
            setChoice={setCvShareChoice}
            onSave={saveCvShare}
            onGenerate={openGeneralCv}
            busy={cvShareBusy}
            note={cvShareNote}
          />

          <section className="dash-card docs-history" id="historique-documents">
            <div className="dash-card-head">
              <h2><Icon d={I.folder} size={16} /> Historique des documents</h2>
              <span className="docs-head-note">
                {filtered.length} sur {docs.length} : télécharger, mettre à jour ou supprimer
              </span>
            </div>

            <div className="docs-history-tools">
              <div className="doc-filters docs-filters">
                <button
                  type="button"
                  className={`doc-filter ${filter === "all" ? "active" : ""}`}
                  onClick={() => setFilter("all")}
                >
                  Tous ({docs.length})
                </button>
                <button
                  type="button"
                  className={`doc-filter ${filter === "cv" ? "active" : ""}`}
                  onClick={() => setFilter("cv")}
                >
                  CV ({cvCount})
                </button>
                <button
                  type="button"
                  className={`doc-filter ${filter === "cover_letter" ? "active" : ""}`}
                  onClick={() => setFilter("cover_letter")}
                >
                  Lettres ({letterCount})
                </button>
              </div>
              <label className="docs-search">
                <Icon d={I.search} size={15} />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Rechercher un document, un modèle…"
                  aria-label="Rechercher dans l'historique"
                />
              </label>
            </div>

            {docs.length === 0 ? (
              <Empty title="L'historique est vide">
                <p>
                  Générez un CV ou une lettre depuis l'atelier : chaque document
                  produit vient ici, prêt à être téléchargé, mis à jour ou
                  supprimé.
                </p>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => switchTab("atelier")}
                >
                  Ouvrir l'atelier <ArrowIcon direction="right" size={11} />
                </button>
              </Empty>
            ) : filtered.length === 0 ? (
              <Empty title="Aucun document ne correspond">
                <p>Modifiez le filtre ou la recherche pour retrouver vos documents.</p>
              </Empty>
            ) : (
              <div className="doc-layout">
                <div className="doc-list">
                  {filtered.map((d) => (
                    <div
                      key={d.id}
                      className={`doc-item${selected?.id === d.id ? " active" : ""}`}
                    >
                      <button
                        type="button"
                        className="doc-item-main"
                        onClick={() => { setSelected(d); setUpdateDoc(null); }}
                      >
                        <span className="doc-item-top">
                          <span className="doc-kind">{d.kind === "cv" ? "CV" : "Lettre"}</span>
                          <AccentDot doc={d} />
                          <span className="doc-model">{nameOf(d)}</span>
                          {sharedCvId === d.id && (
                            <span className="doc-share-flag">
                              <Icon d={I.shield} size={10} /> Partagé
                            </span>
                          )}
                        </span>
                        <span className="doc-item-sub">
                          {docSubtitle(d.title) || d.title}
                        </span>
                        <span className="doc-item-meta">
                          {kindLabel(d)} · {fmtDate(d.created_at)}
                        </span>
                      </button>
                      <div className="doc-item-tools">
                        <button
                          type="button"
                          className="doc-tool"
                          title="Télécharger le PDF"
                          onClick={() => download(d, "pdf")}
                        >
                          <Icon d={I.file} size={12} /> PDF
                        </button>
                        <button
                          type="button"
                          className="doc-tool"
                          title="Mettre à jour depuis votre profil actuel"
                          onClick={() => openUpdate(d)}
                        >
                          <Icon d={I.pen} size={12} /> Mettre à jour
                        </button>
                        {d.kind === "cv" && !d.job_id && (
                          <button
                            type="button"
                            className={`doc-tool${sharedCvId === d.id ? " is-shared" : ""}`}
                            title={sharedCvId === d.id
                              ? "Ce CV est visible par les recruteurs"
                              : "Partager ce CV généraliste avec les recruteurs"}
                            onClick={() => (
                              sharedCvId === d.id ? openSharePanel() : shareDocument(d)
                            )}
                          >
                            <Icon d={I.shield} size={12} />
                            {sharedCvId === d.id ? "Partagé" : "Partager"}
                          </button>
                        )}
                        <button
                          type="button"
                          className="doc-tool danger"
                          title="Supprimer définitivement"
                          onClick={() => removeDoc(d)}
                        >
                          Supprimer
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                {selected && (
                  <div className="doc-view">
                    <div className="doc-view-head">
                      <div className="doc-view-title">
                        <h3>{kindLabel(selected)}</h3>
                        <p className="small muted">
                          Modèle {nameOf(selected)}
                          {" · "}
                          {selected.accent
                            ? `accent ${accentLabel(selected.accent)}`
                            : (selected.template === "ats"
                              ? "turquoise par défaut (ATS)"
                              : "couleur du modèle")}
                          {" · "}{fmtDate(selected.created_at)}
                        </p>
                      </div>
                      <div className="doc-view-actions">
                        <button className="btn btn-primary btn-small" onClick={() => download(selected, "pdf")}>
                          Exporter en PDF (A4)
                        </button>
                        <button className="btn btn-ghost btn-small" onClick={() => download(selected, "md")}>
                          Markdown
                        </button>
                        <button className="btn btn-outline btn-small" onClick={() => openUpdate(selected)}>
                          <Icon d={I.pen} size={12} /> Mettre à jour
                        </button>
                        {selected.kind === "cv" && !selected.job_id && (
                          <button
                            className={`btn btn-small ${sharedCvId === selected.id ? "btn-ghost" : "btn-outline"}`}
                            onClick={() => (
                              sharedCvId === selected.id
                                ? openSharePanel()
                                : shareDocument(selected)
                            )}
                            disabled={cvShareBusy}
                          >
                            <Icon d={I.shield} size={12} />
                            {sharedCvId === selected.id
                              ? "CV partagé"
                              : "Partager avec les recruteurs"}
                          </button>
                        )}
                        <button className="btn btn-ghost btn-small doc-danger" onClick={() => removeDoc(selected)}>
                          Supprimer
                        </button>
                        {selected.job_id && (
                          <Link className="btn btn-ghost btn-small" to={`/opportunites/${selected.job_id}`}>
                            Voir l'offre liée
                          </Link>
                        )}
                      </div>
                    </div>

                    {updatePanelFor(selected)}

                    <div
                      className="doc-content"
                      dangerouslySetInnerHTML={{ __html: mdToHtml(selected.content_markdown) }}
                    />
                  </div>
                )}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
