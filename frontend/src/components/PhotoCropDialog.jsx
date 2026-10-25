import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";
import { ErrorNote } from "./ui.jsx";
import { Icon, I } from "./icons.jsx";

// Recadrage de la photo de profil AVANT envoi : zoom, déplacement,
// aperçu du cercle de l'avatar, puis export carré 512 x 512 en JPEG.
// Rien n'est envoyé tant que le candidat n'a pas validé.
const FRAME = 320;
const OUTPUT = 512;

function coverScale(image) {
  return Math.max(FRAME / image.width, FRAME / image.height);
}

function clampOffset(next, scale, image) {
  const width = image.width * scale;
  const height = image.height * scale;
  const x = width <= FRAME
    ? (FRAME - width) / 2
    : Math.min(0, Math.max(FRAME - width, next.x));
  const y = height <= FRAME
    ? (FRAME - height) / 2
    : Math.min(0, Math.max(FRAME - height, next.y));
  return { x, y };
}

export default function PhotoCropDialog({ file, onClose, onDone }) {
  const canvasRef = useRef(null);
  const imageRef = useRef(null);
  const dragRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    setReady(false);
    let cancelled = false;
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      if (cancelled) return;
      imageRef.current = image;
      const scale = coverScale(image);
      setOffset({
        x: (FRAME - image.width * scale) / 2,
        y: (FRAME - image.height * scale) / 2,
      });
      setZoom(1);
      setReady(true);
    };
    image.onerror = () => {
      if (cancelled) return;
      setError("Image illisible : choisissez un fichier JPG, PNG ou WEBP.");
    };
    image.src = url;
    return () => {
      cancelled = true;
      URL.revokeObjectURL(url);
    };
  }, [file]);

  useEffect(() => {
    const image = imageRef.current;
    const canvas = canvasRef.current;
    if (!ready || !image || !canvas) return;
    const scale = coverScale(image) * zoom;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#0d1f18";
    ctx.fillRect(0, 0, FRAME, FRAME);
    ctx.drawImage(image, offset.x, offset.y, image.width * scale, image.height * scale);
    // Guide circulaire : aperçu du cadrage de l'avatar.
    ctx.save();
    ctx.strokeStyle = "rgba(255, 255, 255, 0.72)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(FRAME / 2, FRAME / 2, FRAME / 2 - 6, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }, [ready, zoom, offset]);

  useEffect(() => {
    function onKey(event) {
      if (event.key === "Escape" && !busy) onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  const changeZoom = useCallback((nextZoom) => {
    const image = imageRef.current;
    if (!image) return;
    const base = coverScale(image);
    const oldScale = base * zoom;
    const newScale = base * nextZoom;
    const centerX = (FRAME / 2 - offset.x) / oldScale;
    const centerY = (FRAME / 2 - offset.y) / oldScale;
    const next = {
      x: FRAME / 2 - centerX * newScale,
      y: FRAME / 2 - centerY * newScale,
    };
    setZoom(nextZoom);
    setOffset(clampOffset(next, newScale, image));
  }, [offset, zoom]);

  function recenter() {
    const image = imageRef.current;
    if (!image) return;
    const scale = coverScale(image) * zoom;
    setOffset({
      x: (FRAME - image.width * scale) / 2,
      y: (FRAME - image.height * scale) / 2,
    });
  }

  function onPointerDown(event) {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      originX: offset.x,
      originY: offset.y,
    };
  }

  function onPointerMove(event) {
    if (!dragRef.current || !imageRef.current) return;
    const image = imageRef.current;
    const scale = coverScale(image) * zoom;
    setOffset(clampOffset({
      x: dragRef.current.originX + (event.clientX - dragRef.current.startX),
      y: dragRef.current.originY + (event.clientY - dragRef.current.startY),
    }, scale, image));
  }

  function onPointerUp() {
    dragRef.current = null;
  }

  function validate() {
    const image = imageRef.current;
    if (!image) return;
    setBusy(true);
    setError("");
    const scale = coverScale(image) * zoom;
    const canvas = document.createElement("canvas");
    canvas.width = OUTPUT;
    canvas.height = OUTPUT;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, OUTPUT, OUTPUT);
    const ratio = OUTPUT / FRAME;
    ctx.drawImage(
      image,
      offset.x * ratio,
      offset.y * ratio,
      image.width * scale * ratio,
      image.height * scale * ratio,
    );
    canvas.toBlob(async (blob) => {
      if (!blob) {
        setError("Recadrage impossible : réessayez avec une autre image.");
        setBusy(false);
        return;
      }
      try {
        const form = new FormData();
        form.append("file", new File([blob], "photo-recadree.jpg", { type: "image/jpeg" }));
        await api("/profile/photo", { method: "POST", form });
        onDone();
      } catch (err) {
        setError(err.detail || "Envoi de la photo impossible");
      } finally {
        setBusy(false);
      }
    }, "image/jpeg", 0.92);
  }

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <div className="modal photo-crop-modal" role="dialog" aria-modal="true" aria-labelledby="crop-title">
        <h2 id="crop-title">Recadrer la photo de profil</h2>
        <p className="small muted">
          Déplacez l'image, ajustez le zoom, puis validez. Le cercle indique
          le cadrage de votre avatar.
        </p>

        <div className="photo-crop-stage">
          {ready ? (
            <canvas
              ref={canvasRef}
              width={FRAME}
              height={FRAME}
              className="photo-crop-canvas"
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerCancel={onPointerUp}
              aria-label="Aperçu de la photo à recadrer"
            />
          ) : (
            <div className="photo-crop-loading">Chargement de l'image…</div>
          )}
        </div>

        <div className="photo-crop-controls">
          <label className="photo-crop-zoom">
            <span>Zoom</span>
            <input
              type="range"
              min="1"
              max="3"
              step="0.02"
              value={zoom}
              onChange={(e) => changeZoom(Number(e.target.value))}
              disabled={!ready || busy}
            />
          </label>
          <button type="button" className="btn btn-ghost btn-small" onClick={recenter} disabled={!ready || busy}>
            <Icon d={I.target} size={13} /> Recentrer
          </button>
        </div>

        <ErrorNote error={error} />

        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={busy}>
            Annuler
          </button>
          <button type="button" className="btn btn-primary" onClick={validate} disabled={!ready || busy}>
            {busy ? "Envoi…" : "Valider la photo"}
          </button>
        </div>
      </div>
    </div>
  );
}
