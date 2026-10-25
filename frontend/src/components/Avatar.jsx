import { useEffect, useState } from "react";
import { apiRaw } from "../api/client.js";

// Photo de profil : les endpoints photo sont protégés (jeton Bearer),
// donc on la charge en blob puis on l'affiche via une URL locale.
// Repli sur les initiales quand aucune photo n'est disponible.
function initialsOf(name = "") {
  return name
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export default function Avatar({
  name,
  photoUrl,
  className = "talent-avatar",
  title,
}) {
  const [src, setSrc] = useState("");

  useEffect(() => {
    let active = true;
    let objectUrl = "";
    setSrc("");
    if (!photoUrl) return undefined;
    const path = photoUrl.replace(/^\/api/, "");
    apiRaw(path)
      .then(async (res) => {
        if (!res.ok || !active) return;
        const blob = await res.blob();
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch(() => {});
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [photoUrl]);

  return (
    <div className={className} title={title} aria-hidden="true">
      {src ? <img src={src} alt="" /> : <span>{initialsOf(name)}</span>}
    </div>
  );
}
