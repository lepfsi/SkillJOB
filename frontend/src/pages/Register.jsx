import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { api } from "../api/client.js";

// Inscription : candidat ou recruteur (entreprise), avec genre et
// localisation structurée (région -> département -> arrondissement -> ville).

function GeoSelects({ geo, value, onChange }) {
  const region = value.region || "";
  const department = value.department || "";
  const departments = geo
    .find((r) => r.name === region)?.departments || [];
  const arrondissements = departments
    .find((d) => d.name === department)?.arrondissements || [];

  return (
    <>
      <label className="field">
        <span>Région *</span>
        <select
          value={region}
          required
          onChange={(e) => onChange({ region: e.target.value, department: "", arrondissement: "" })}
        >
          <option value="">Choisir une région</option>
          {geo.map((r) => <option key={r.name}>{r.name}</option>)}
        </select>
      </label>
      <label className="field">
        <span>Département *</span>
        <select
          value={department}
          required
          disabled={!region}
          onChange={(e) => onChange({ department: e.target.value, arrondissement: "" })}
        >
          <option value="">{region ? "Choisir un département" : "Choisissez d'abord la région"}</option>
          {departments.map((d) => <option key={d.name}>{d.name}</option>)}
        </select>
      </label>
      <label className="field">
        <span>Arrondissement *</span>
        <select
          value={value.arrondissement || ""}
          required
          disabled={!department}
          onChange={(e) => onChange({ arrondissement: e.target.value })}
        >
          <option value="">{department ? "Choisir un arrondissement" : "Choisissez d'abord le département"}</option>
          {arrondissements.map((a) => <option key={a}>{a}</option>)}
        </select>
      </label>
      <label className="field">
        <span>Ville / quartier (saisie libre) *</span>
        <input
          value={value.city || ""}
          required
          onChange={(e) => onChange({ city: e.target.value })}
          placeholder="Ex. Akwa, Ndogbong, Bonabéri…"
        />
      </label>
    </>
  );
}

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [accountType, setAccountType] = useState("candidate");
  const [geo, setGeo] = useState(null);
  const [form, setForm] = useState({
    fullName: "", email: "", password: "", gender: "",
    region: "", department: "", arrondissement: "", city: "",
    recruiterType: "company",
    companyName: "", companySector: "", companyDescription: "", companyLocation: "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/geo").then((d) => setGeo(d.regions)).catch(() => setGeo([]));
  }, []);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (accountType === "recruiter") {
        const independent = form.recruiterType === "independent";
        await register({
          full_name: independent ? form.fullName.trim() : "",
          recruiter_type: form.recruiterType,
          email: form.email.trim(),
          password: form.password,
          gender: independent ? form.gender || null : null,
          region: independent ? form.region || null : null,
          department: independent ? form.department || null : null,
          arrondissement: independent ? form.arrondissement || null : null,
          city: independent ? form.city || null : null,
          company_name: form.companyName.trim(),
          company_sector: form.companySector.trim(),
          company_description: form.companyDescription.trim(),
          company_location: form.companyLocation.trim(),
        });
        navigate("/recruteur");
      } else {
        await register({
          full_name: form.fullName.trim(),
          email: form.email.trim(),
          password: form.password,
          gender: form.gender || null,
          region: form.region || null,
          department: form.department || null,
          arrondissement: form.arrondissement || null,
          city: form.city || null,
        });
        navigate("/onboarding");
      }
    } catch (err) {
      setError(err.detail || "Inscription impossible");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <form className="auth-card" onSubmit={onSubmit}>
        <div className="auth-brand">
          OrientSkill <span>AI</span>
        </div>
        <p className="auth-tagline">Créez votre compte en moins d'une minute.</p>
        {error && <div className="alert alert-error">{error}</div>}

        <div className="field-label" style={{ marginBottom: "0.4rem" }}>Je m'inscris comme :</div>
        <div className="inline-fields" style={{ marginBottom: "0.6rem" }}>
          <label className="check">
            <input
              type="radio"
              checked={accountType === "candidate"}
              onChange={() => setAccountType("candidate")}
            />
            Candidat
          </label>
          <label className="check">
            <input
              type="radio"
              checked={accountType === "recruiter"}
              onChange={() => setAccountType("recruiter")}
            />
            Recruteur / entreprise
          </label>
        </div>

        {accountType === "candidate" && (
          <>
            <label className="field">
              <span>Nom complet *</span>
              <input value={form.fullName} onChange={(e) => set("fullName", e.target.value)} required placeholder="Ex. Steve Nguema" />
            </label>
            <div className="grid-2">
              <label className="field">
                <span>Adresse e-mail *</span>
                <input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required placeholder="vous@exemple.cm" />
              </label>
              <label className="field">
                <span>Mot de passe * (4 caractères min.)</span>
                <input type="password" value={form.password} onChange={(e) => set("password", e.target.value)} required minLength="4" />
              </label>
            </div>
            <label className="field">
              <span>Vous êtes *</span>
              <select value={form.gender} onChange={(e) => set("gender", e.target.value)} required>
                <option value="">Choisir</option>
                <option value="homme">Un homme</option>
                <option value="femme">Une femme</option>
              </select>
            </label>
            <div className="field-label">Localisation *</div>
            {geo ? (
              <GeoSelects geo={geo} value={form} onChange={(patch) => setForm((f) => ({ ...f, ...patch }))} />
            ) : (
              <p className="muted small">Chargement des régions…</p>
            )}
          </>
        )}

        {accountType === "recruiter" && (
          <>
            <div className="field-label" style={{ marginTop: "0.4rem" }}>Type de compte recruteur</div>
            <div className="inline-fields" style={{ marginBottom: "0.6rem" }}>
              <label className="check">
                <input
                  type="radio"
                  checked={form.recruiterType === "company"}
                  onChange={() => set("recruiterType", "company")}
                />
                Entreprise
              </label>
              <label className="check">
                <input
                  type="radio"
                  checked={form.recruiterType === "agency"}
                  onChange={() => set("recruiterType", "agency")}
                />
                Cabinet RH
              </label>
              <label className="check">
                <input
                  type="radio"
                  checked={form.recruiterType === "independent"}
                  onChange={() => set("recruiterType", "independent")}
                />
                Recruteur indépendant
              </label>
            </div>
            <p className="small muted">
              {form.recruiterType === "independent"
                ? "Recruteur indépendant : inscription complète (nom, genre, localisation)."
                : "Le compte représente la structure : aucun champ personnel demandé, le nom affiché sera celui de la structure."}
            </p>
            {form.recruiterType === "independent" && (
              <>
                <label className="field">
                  <span>Nom complet *</span>
                  <input value={form.fullName} onChange={(e) => set("fullName", e.target.value)} required placeholder="Ex. Jean Mbarga" />
                </label>
                <label className="field">
                  <span>Vous êtes *</span>
                  <select value={form.gender} onChange={(e) => set("gender", e.target.value)} required>
                    <option value="">Choisir</option>
                    <option value="homme">Un homme</option>
                    <option value="femme">Une femme</option>
                  </select>
                </label>
                <div className="field-label">Localisation *</div>
                {geo ? (
                  <GeoSelects geo={geo} value={form} onChange={(patch) => setForm((f) => ({ ...f, ...patch }))} />
                ) : (
                  <p className="muted small">Chargement des régions…</p>
                )}
              </>
            )}
            <label className="field">
              <span>Adresse e-mail professionnelle *</span>
              <input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required placeholder="rh@entreprise.cm" />
            </label>
            <label className="field">
              <span>Mot de passe * (4 caractères min.)</span>
              <input type="password" value={form.password} onChange={(e) => set("password", e.target.value)} required minLength="4" />
            </label>
            <div className="field-label" style={{ marginTop: "0.4rem" }}>Votre structure</div>
            <label className="field">
              <span>Nom de l'{form.recruiterType === "agency" ? "agence" : "entreprise"} *</span>
              <input value={form.companyName} onChange={(e) => set("companyName", e.target.value)} required placeholder="Ex. Numérik Services CM" />
            </label>
            <div className="grid-2">
              <label className="field">
                <span>Secteur d'activité</span>
                <input value={form.companySector} onChange={(e) => set("companySector", e.target.value)} placeholder="Informatique / IT" />
              </label>
              <label className="field">
                <span>Localisation de la structure</span>
                <input value={form.companyLocation} onChange={(e) => set("companyLocation", e.target.value)} placeholder="Douala" />
              </label>
            </div>
            <label className="field">
              <span>Présentation de la structure</span>
              <textarea rows="2" value={form.companyDescription} onChange={(e) => set("companyDescription", e.target.value)} />
            </label>
          </>
        )}

        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? "Création…" : "Créer mon compte"}
        </button>
        <p className="auth-alt">
          Déjà inscrit ? <Link to="/login">Se connecter</Link>
        </p>
      </form>
    </div>
  );
}
