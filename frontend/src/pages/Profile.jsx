import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api, apiRaw } from "../api/client.js";
import ProfileEditor from "../components/ProfileEditor.jsx";
import { sanitizeProfile, VERIFICATION_LABELS } from "../lib.js";
import { useAuth } from "../context/AuthContext.jsx";
import { Loader, ErrorNote, Empty } from "../components/ui.jsx";

// Carte de profil présentable (photo, badge de vérification) + édition
// complète + sécurité (MFA) + vérification d'identité.

function ProfileCard({ user, profile, photoUrl, onPhotoUploaded, verified }) {
  const geo = [
    user.city, user.arrondissement, user.department, user.region,
  ].filter(Boolean).join(" · ");
  return (
    <div className="profile-card">
      {photoUrl
        ? <img className="profile-card-photo" src={photoUrl} alt={user.full_name} />
        : (
          <div className="profile-card-photo-placeholder">
            Photo<br />de profil
          </div>
        )}
      <div style={{ flex: 1 }}>
        <h1 style={{ marginBottom: 0 }}>{user.full_name}</h1>
        <p className="job-meta" style={{ margin: "0.2rem 0" }}>
          {profile?.title || "Profil en construction"}
          {geo ? ` · ${geo}` : ""}
        </p>
        <div className="chip-row" style={{ marginTop: "0.4rem" }}>
          {verified
            ? <span className="verified-chip">Profil vérifié</span>
            : <span className="badge badge-none">{VERIFICATION_LABELS[user.verification_status] || "Non vérifié"}</span>}
        </div>
        <label className="btn btn-ghost btn-small" style={{ marginTop: "0.7rem", cursor: "pointer" }}>
          {photoUrl ? "Changer la photo" : "Ajouter une photo"}
          <input
            type="file"
            accept=".jpg,.jpeg,.png,.webp"
            style={{ display: "none" }}
            onChange={onPhotoUploaded}
          />
        </label>
        <p className="small muted" style={{ marginTop: "0.3rem" }}>
          La photo apparaît sur votre profil et dans vos CV exportés.
        </p>
      </div>
    </div>
  );
}

export default function Profile() {
  const navigate = useNavigate();
  const { user, setUser } = useAuth();
  const [profile, setProfile] = useState(undefined);
  const [photoUrl, setPhotoUrl] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [verifStatus, setVerifStatus] = useState("none");

  const reloadUser = () => {
    api("/auth/me").then((u) => {
      setUser(u);
      localStorage.setItem("orientskill_user", JSON.stringify(u));
      setVerifStatus(u.verification_status || "none");
      if (u.photo_path) {
        apiRaw("/profile/photo").then((res) => {
          if (res.ok) return res.blob().then((b) => setPhotoUrl(URL.createObjectURL(b)));
          setPhotoUrl(null);
        }).catch(() => setPhotoUrl(null));
      } else {
        setPhotoUrl(null);
      }
    }).catch(() => {});
  };

  useEffect(() => {
    api("/profile").then(setProfile).catch(() => setProfile(null));
    api("/profile/verification")
      .then((v) => setVerifStatus(v.status))
      .catch(() => {});
    reloadUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function uploadPhoto(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const form = new FormData();
      form.append("file", file);
      await api("/profile/photo", { method: "POST", form });
      reloadUser();
    } catch (err) {
      setError(err.detail);
    }
  }

  async function save() {
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const updated = await api("/profile", {
        method: "PUT",
        body: sanitizeProfile(profile),
      });
      setProfile(updated);
      setSaved(true);
    } catch (err) {
      setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  if (profile === undefined) {
    return <div className="page"><Loader /></div>;
  }

  return (
    <div className="page">
      <h1>Profil</h1>
      <p className="page-lead">
        La source de vérité de la plateforme. Le système ne génère jamais
        d'information qui ne figure pas ici.
      </p>

      <ProfileCard
        user={user || {}}
        profile={profile}
        photoUrl={photoUrl}
        onPhotoUploaded={uploadPhoto}
        verified={verifStatus === "verified"}
      />

      {saved && <div className="alert alert-success">Profil enregistré.</div>}
      <ErrorNote error={error} />

      {profile === null ? (
        <Empty title="Aucun profil pour le moment">
          <p>Construisez votre profil professionnel pour activer les recommandations.</p>
          <button className="btn btn-primary" onClick={() => navigate("/onboarding")}>
            Construire mon profil
          </button>
        </Empty>
      ) : (
        <>
          <ProfileEditor profile={profile} onChange={setProfile} />
          <div className="actions-row">
            <button className="btn btn-primary" onClick={save} disabled={busy}>
              {busy ? "Enregistrement…" : "Enregistrer mon profil"}
            </button>
          </div>
        </>
      )}

      <div className="panel">
        <h2>Paramètres du compte</h2>
        <p className="small muted">
          Sécurité (MFA), notifications et vérification de profil se
          gèrent dans les paramètres de votre compte.
        </p>
        <Link className="btn btn-outline" to="/parametres-compte">
          Ouvrir mes paramètres
        </Link>
      </div>
    </div>
  );
}
