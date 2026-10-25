import { useState } from "react";

// Aperçu RÉEL du rendu PDF (capture d'un exemple fictif, jamais des
// données utilisateur). Si l'image manque, on retombe sur la miniature
// squelette : la galerie ne casse jamais.
export default function PreviewImage({ src, alt, fallback, className, loading = "lazy" }) {
  const [failed, setFailed] = useState(false);
  if (failed) return fallback || null;
  return (
    <img
      src={src}
      alt={alt}
      className={className}
      loading={loading}
      onError={() => setFailed(true)}
    />
  );
}
