import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { fmtDate } from "../lib.js";
import { Icon, I } from "./icons.jsx";
import { ErrorNote, Loader } from "./ui.jsx";

// Import d'un CV dans le profil, depuis la bibliothèque de documents ou
// depuis l'ordinateur. L'analyse produit un brouillon : la page Profil
// affiche les ajouts proposés et rien n'est enregistré avant validation.
export default function CvImportDialog({ open, onClose, onAnalyzed }) {
  const [source, setSource] = useState("library");
  const [documents, setDocuments] = useState(null);
  const [selectedId, setSelectedId] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    setSource("library");
    setDocuments(null);
    setSelectedId("");
    setFile(null);
    setBusy(false);
    setError("");
    api("/documents")
      .then((items) => {
        const cvs = (items || [])
          .filter((item) => item.kind === "cv")
          .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        setDocuments(cvs);
      })
      .catch((err) => {
        setDocuments([]);
        setError(err.detail);
      });
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    function onKey(event) {
      if (event.key === "Escape" && !busy) onClose();
    }
    window.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open, busy, onClose]);

  if (!open) return null;

  function chooseFile(event) {
    const next = event.target.files?.[0] || null;
    setError("");
    if (!next) {
      setFile(null);
      return;
    }
    if (!/\.(pdf|txt)$/i.test(next.name)) {
      setFile(null);
      setError("Choisissez un fichier PDF ou TXT.");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }
    if (next.size > 10 * 1024 * 1024) {
      setFile(null);
      setError("Le fichier dépasse 10 Mo.");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }
    setFile(next);
  }

  async function analyze() {
    setBusy(true);
    setError("");
    try {
      let response;
      let label;
      if (source === "library") {
        const document = documents?.find((item) => String(item.id) === selectedId);
        response = await api("/profile/import-cv/library", {
          method: "POST",
          body: { document_id: Number(selectedId) },
        });
        label = document?.title || "CV de ma bibliothèque";
      } else {
        if (!file) return;
        const form = new FormData();
        form.append("file", file);
        response = await api("/profile/import-cv", { method: "POST", form });
        label = file.name;
      }
      onAnalyzed(response, label);
    } catch (err) {
      setError(err.detail);
      setBusy(false);
    }
  }

  const canAnalyze = source === "library" ? !!selectedId : !!file;
  const selectedDocument = documents?.find((item) => String(item.id) === selectedId);

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <div
        className="modal cv-import-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="cv-import-title"
      >
        <div className="cv-import-head">
          <span className="cv-import-head-icon"><Icon d={I.file} size={20} /></span>
          <div>
            <h2 id="cv-import-title">Importer un CV dans mon profil</h2>
            <p className="small muted">
              L'analyse produit un brouillon. Rien n'est enregistré avant votre validation.
            </p>
          </div>
        </div>

        <div className="cv-import-sources" role="tablist" aria-label="Source du CV">
          <button
            type="button"
            role="tab"
            aria-selected={source === "library"}
            className={source === "library" ? "active" : ""}
            onClick={() => {
              setSource("library");
              setError("");
            }}
            disabled={busy}
          >
            <Icon d={I.book} size={16} />
            <span>Ma bibliothèque</span>
            <small>Choisir un CV déjà généré</small>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={source === "pc"}
            className={source === "pc" ? "active" : ""}
            onClick={() => {
              setSource("pc");
              setError("");
            }}
            disabled={busy}
          >
            <Icon d={I.file} size={16} />
            <span>Mon ordinateur</span>
            <small>PDF ou TXT, 10 Mo max</small>
          </button>
        </div>

        {source === "library" ? (
          <div className="cv-import-panel" role="tabpanel" aria-label="CV de ma bibliothèque">
            {documents === null && <Loader />}
            {documents && documents.length === 0 && (
              <div className="cv-import-empty">
                <p>Aucun CV dans votre bibliothèque pour le moment.</p>
                <Link className="link-more" to="/documents" onClick={onClose}>
                  Ouvrir mes documents
                </Link>
              </div>
            )}
            {documents && documents.length > 0 && (
              <div className="cv-import-docs" role="radiogroup" aria-label="CV disponibles">
                {documents.map((document) => (
                  <button
                    type="button"
                    key={document.id}
                    className={`cv-import-doc${String(document.id) === selectedId ? " is-selected" : ""}`}
                    role="radio"
                    aria-checked={String(document.id) === selectedId}
                    onClick={() => setSelectedId(String(document.id))}
                    disabled={busy}
                  >
                    <span className="cv-import-doc-icon"><Icon d={I.file} size={17} /></span>
                    <span className="cv-import-doc-body">
                      <strong>{document.title}</strong>
                      <span className="opp-meta">
                        {[document.job_id ? "CV ciblé" : "CV généraliste", fmtDate(document.created_at)]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    </span>
                    <span className="cv-import-radio" aria-hidden="true" />
                  </button>
                ))}
              </div>
            )}
            {selectedDocument && (
              <p className="cv-import-note">
                Le CV choisi sera analysé pour compléter votre profil. Les informations
                déjà présentes ne seront pas écrasées.
              </p>
            )}
          </div>
        ) : (
          <div className="cv-import-panel" role="tabpanel" aria-label="CV de mon ordinateur">
            <label className={`cv-import-drop${file ? " has-file" : ""}`}>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.txt,application/pdf,text/plain"
                onChange={chooseFile}
                disabled={busy}
              />
              <span className="cv-import-drop-icon"><Icon d={I.file} size={22} /></span>
              <strong>{file ? "Changer de fichier" : "Choisir un fichier PDF ou TXT"}</strong>
              <span className="small muted">
                Votre CV reste privé. Seul le brouillon de profil sera proposé.
              </span>
            </label>
            {file && (
              <div className="cv-import-file">
                <Icon d={I.file} size={16} />
                <span>{file.name}</span>
                <button
                  type="button"
                  className="btn btn-ghost btn-small"
                  onClick={() => {
                    setFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = "";
                  }}
                  disabled={busy}
                >
                  Retirer
                </button>
              </div>
            )}
          </div>
        )}

        <ErrorNote error={error} />

        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={busy}>
            Annuler
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={analyze}
            disabled={busy || !canAnalyze}
          >
            {busy
              ? "Analyse en cours…"
              : source === "library"
                ? "Analyser ce CV"
                : "Analyser mon CV"}
          </button>
        </div>
      </div>
    </div>
  );
}
