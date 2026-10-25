import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, apiHref } from "../api/client.js";
import { Loader, ErrorNote } from "../components/ui.jsx";

// Visuel public de candidature par e-mail, prêt pour LinkedIn. Le SVG est
// généré par le backend (adresse interne + référence de l'offre) puis
// converti en PNG dans le navigateur : aucune ressource externe.

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function safeName(value) {
  return (value || "offre")
    .normalize("NFKD")
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-")
    .toLowerCase()
    .slice(0, 60) || "offre";
}

export default function Poster() {
  const { jobId } = useParams();
  const [job, setJob] = useState(null);
  const [svg, setSvg] = useState("");
  const [svgUrl, setSvgUrl] = useState("");
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [copied, setCopied] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    let active = true;
    let localUrl = "";
    Promise.all([
      api(`/public/jobs/${jobId}`),
      fetch(apiHref(`/public/jobs/${jobId}/poster.svg`)),
    ])
      .then(async ([jobData, response]) => {
        if (!response.ok) {
          let detail = "Visuel indisponible.";
          try {
            const body = await response.json();
            detail = body.detail || detail;
          } catch {
            // Réponse non JSON : on garde le message générique.
          }
          throw new Error(detail);
        }
        const text = await response.text();
        if (!active) return;
        localUrl = URL.createObjectURL(new Blob([text], { type: "image/svg+xml" }));
        setJob(jobData);
        setSvg(text);
        setSvgUrl(localUrl);
      })
      .catch((err) => {
        if (active) setError(err.detail || err.message || "Visuel indisponible");
      });
    return () => {
      active = false;
      if (localUrl) URL.revokeObjectURL(localUrl);
    };
  }, [jobId]);

  const publicUrl = useMemo(
    () => `${window.location.origin}/postuler/${jobId}`,
    [jobId]
  );

  const suggestedText = useMemo(() => {
    if (!job) return "";
    return [
      `Nous recrutons : ${job.title}`,
      `${job.company} · ${job.location || "Cameroun"} · ${job.contract_type}`,
      "",
      "Envoyez votre CV et votre lettre à :",
      job.email_apply_address,
      "",
      `Objet : CANDIDATURE ${job.email_reference} - ${job.title}`,
      "",
      `Détails et candidature : ${publicUrl}`,
    ].join("\n");
  }, [job, publicUrl]);

  async function copy(value, label) {
    setActionError("");
    try {
      await navigator.clipboard.writeText(value);
      setCopied(label);
      window.setTimeout(() => setCopied(""), 2500);
    } catch {
      setActionError("Copie impossible : sélectionnez le texte et copiez-le manuellement.");
    }
  }

  function downloadSvg() {
    if (!svg || !job) return;
    downloadBlob(
      new Blob([svg], { type: "image/svg+xml;charset=utf-8" }),
      `visuel-${safeName(job.email_reference || job.title)}.svg`
    );
  }

  async function downloadPng() {
    if (!svgUrl || !job) return;
    setBusy("png");
    setActionError("");
    try {
      const image = new Image();
      image.src = svgUrl;
      await new Promise((resolve, reject) => {
        image.onload = resolve;
        image.onerror = () => reject(new Error("Conversion du visuel impossible."));
      });
      const canvas = document.createElement("canvas");
      canvas.width = 1200;
      canvas.height = 1500;
      const context = canvas.getContext("2d");
      context.fillStyle = "#ffffff";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
      if (!blob) throw new Error("Conversion PNG impossible.");
      downloadBlob(
        blob,
        `visuel-${safeName(job.email_reference || job.title)}.png`
      );
    } catch (err) {
      setActionError(err.message || "Téléchargement impossible.");
    } finally {
      setBusy("");
    }
  }

  if (error) {
    return (
      <div className="poster-page">
        <header className="poster-top">
          <Link to={`/postuler/${jobId}`} className="auth-brand">OrientSkill <span>AI</span></Link>
          <Link to={`/postuler/${jobId}`} className="btn btn-ghost btn-small">Retour à l'offre</Link>
        </header>
        <main className="poster-error">
          <ErrorNote error={error} />
          <p className="small muted">
            L'adresse de réception e-mail se configure dans la console
            d'administration, rubrique Réception des candidatures.
          </p>
          <Link className="btn btn-outline" to={`/postuler/${jobId}`}>
            Retour à la fiche de l'offre
          </Link>
        </main>
      </div>
    );
  }

  if (!job || !svgUrl) {
    return <div className="poster-page"><Loader /></div>;
  }

  return (
    <div className="poster-page">
      <header className="poster-top">
        <Link to={`/postuler/${jobId}`} className="auth-brand">OrientSkill <span>AI</span></Link>
        <div className="actions-row" style={{ marginTop: 0 }}>
          <Link className="btn btn-ghost btn-small" to={`/postuler/${jobId}`}>
            Voir l'offre
          </Link>
          <Link className="btn btn-outline btn-small" to="/login">
            Se connecter
          </Link>
        </div>
      </header>

      <main className="poster-shell">
        <section className="poster-preview" aria-label="Aperçu du visuel">
          <img src={svgUrl} alt={`Visuel de candidature pour ${job.title}`} />
        </section>

        <aside className="poster-side">
          <span className="poster-kicker">Candidature par e-mail</span>
          <h1>{job.title}</h1>
          <p className="small muted">
            {job.company} · {job.location || "Cameroun"} · {job.contract_type}
          </p>
          <p className="poster-lead">
            Publiez ce visuel sur LinkedIn ou WhatsApp. Les candidats envoient
            leur CV et leur lettre à l'adresse interne avec la référence de
            l'offre : la candidature est transmise automatiquement à
            l'entreprise.
          </p>

          <div className="poster-recap">
            <span>Adresse de réception</span>
            <strong>{job.email_apply_address}</strong>
            <span>Référence à mettre dans l'objet</span>
            <strong>{job.email_reference}</strong>
          </div>

          <ErrorNote error={actionError} />

          <div className="poster-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={downloadPng}
              disabled={busy === "png"}
            >
              {busy === "png" ? "Préparation…" : "Télécharger en PNG"}
            </button>
            <button type="button" className="btn btn-outline" onClick={downloadSvg}>
              Télécharger en SVG
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => copy(suggestedText, "texte")}
            >
              {copied === "texte" ? "Texte copié" : "Copier le texte de publication"}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => copy(publicUrl, "lien")}
            >
              {copied === "lien" ? "Lien copié" : "Copier le lien de candidature"}
            </button>
          </div>

          <label className="field">
            <span>Texte prêt à publier</span>
            <textarea className="poster-copy" readOnly value={suggestedText} />
          </label>

          <p className="poster-note">
            Le PNG est au format 1200 x 1500, adapté à LinkedIn. Vérifiez les
            informations de l'offre avant publication : le visuel reprend
            uniquement les données de la fiche.
          </p>
        </aside>
      </main>
    </div>
  );
}
