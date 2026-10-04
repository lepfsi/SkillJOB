import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, apiRaw } from "../api/client.js";
import { mdToHtml, fmtDate } from "../lib.js";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";

// Page Documents / CV (§35) : versions ciblées, type, offre liée, date,
// export Markdown et PDF A4 aux normes.
function docSubtitle(title) {
  const parts = title.split(" · ");
  return parts.slice(1).join(" · ");
}

export default function Documents() {
  const [docs, setDocs] = useState(null);
  const [selected, setSelected] = useState(null);
  const [filter, setFilter] = useState("all"); // all | cv | cover_letter
  const [error, setError] = useState("");
  const [searchParams] = useSearchParams();

  useEffect(() => {
    api("/documents")
      .then((list) => {
        setDocs(list);
        const openId = Number(searchParams.get("open"));
        const found = list.find((d) => d.id === openId);
        if (found) setSelected(found);
        else if (list.length > 0) setSelected(list[0]);
      })
      .catch((e) => setError(e.detail));
  }, [searchParams]);

  const filtered = useMemo(() => {
    if (!docs) return [];
    if (filter === "all") return docs;
    return docs.filter((d) => d.kind === filter);
  }, [docs, filter]);

  async function download(doc, format) {
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
      setError(err.message || "Téléchargement impossible");
    }
  }

  if (error && !docs) {
    return <div className="page"><ErrorNote error={error} /></div>;
  }
  if (!docs) {
    return <div className="page"><Loader /></div>;
  }

  return (
    <div className="page">
      <h1>Documents</h1>
      <p className="page-lead">
        Vos CV ciblés et lettres de motivation, générés uniquement à partir
        de votre profil validé. Le PDF suit la mise en page A4
        professionnelle.
      </p>
      <ErrorNote error={error} />

      {docs.length === 0 ? (
        <Empty title="Aucun document pour le moment">
          <p>
            Choisissez une opportunité puis cliquez sur « Créer mon CV ciblé »
            ou « Lettre de motivation ».
          </p>
          <Link className="btn btn-outline" to="/opportunites">Parcourir les offres</Link>
        </Empty>
      ) : (
        <>
          <div className="doc-toolbar">
            <div className="doc-filters">
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
                CV ({docs.filter((d) => d.kind === "cv").length})
              </button>
              <button
                type="button"
                className={`doc-filter ${filter === "cover_letter" ? "active" : ""}`}
                onClick={() => setFilter("cover_letter")}
              >
                Lettres ({docs.filter((d) => d.kind === "cover_letter").length})
              </button>
            </div>
          </div>

          <div className="doc-layout">
            <div className="doc-list">
              {filtered.map((d) => (
              <button
                key={d.id}
                type="button"
                className={`doc-item${selected?.id === d.id ? " active" : ""}`}
                onClick={() => setSelected(d)}
              >
                <span className="doc-kind">
                  {d.kind === "cv" ? "CV" : d.kind === "business_plan" ? "Business plan" : "Lettre"}
                  {d.template === "ats" ? " · ATS" : d.template === "moderne" ? " · Moderne" : ""}
                </span>
                <div className="small">{docSubtitle(d.title) || d.title}</div>
                <div className="small muted">{fmtDate(d.created_at)}</div>
              </button>
              ))}
            </div>

            {selected && (
              <div className="doc-view">
                <div className="actions-row" style={{ marginTop: 0 }}>
                  <button className="btn btn-primary btn-small" onClick={() => download(selected, "pdf")}>
                    Exporter en PDF (A4)
                  </button>
                  <button className="btn btn-ghost btn-small" onClick={() => download(selected, "md")}>
                    Exporter en Markdown
                  </button>
                  {selected.job_id && (
                    <Link className="btn btn-ghost btn-small" to={`/opportunites/${selected.job_id}`}>
                      Voir l'offre liée
                    </Link>
                  )}
                </div>
                <div
                  className="doc-content"
                  dangerouslySetInnerHTML={{ __html: mdToHtml(selected.content_markdown) }}
                />
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
