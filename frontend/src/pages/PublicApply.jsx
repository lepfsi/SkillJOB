import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, setSession } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { Icon, I, ArrowIcon } from "../components/icons.jsx";
import { Loader, ErrorNote } from "../components/ui.jsx";
import JobPublicView from "../components/JobPublicView.jsx";

// Candidature publique depuis le lien d'une offre. Un candidat non inscrit
// saisit nom, e-mail et téléphone : le compte est créé, la candidature
// enregistrée, et il complète son profil ensuite. Aucune donnée inventée.
export default function PublicApply() {
  const { jobId } = useParams();
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    fullName: "", email: "", phone: "", motivation: "",
  });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);

  useEffect(() => {
    api(`/public/jobs/${jobId}`)
      .then(setJob)
      .catch((e) => setError(e.detail || "Offre introuvable"));
  }, [jobId]);

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api(`/public/jobs/${jobId}/apply`, {
        method: "POST",
        body: {
          full_name: form.fullName.trim(),
          email: form.email.trim(),
          phone: form.phone.trim(),
          motivation: form.motivation.trim(),
        },
      });
      setSession(res.token, res.user);
      setUser(res.user);
      setDone(res);
    } catch (err) {
      setError(err.detail || "Candidature impossible");
    } finally {
      setBusy(false);
    }
  }

  if (!job && !error) {
    return <div className="public-apply"><Loader /></div>;
  }

  return (
    <div className="public-apply">
      <header className="public-apply-head">
        <Link to="/" className="auth-brand">OrientSkill <span>AI</span></Link>
        <Link to="/login" className="btn btn-ghost btn-small">Se connecter</Link>
      </header>

      <main className="public-apply-main">
        {job && <JobPublicView job={job} />}

        <section className="public-form-card">
          <ErrorNote error={error} />

          {job && job.apply_channel !== "platform" ? (
            <div>
              <h2>Postuler auprès de l'entreprise</h2>
              <p className="small muted">
                Cette offre se postule directement auprès de l'entreprise.
                Le lien officiel est indiqué ci-dessous : aucune candidature
                n'est enregistrée par OrientSkill AI pour cette annonce.
              </p>
              {job.apply_instructions && (
                <p className="small">{job.apply_instructions}</p>
              )}
              {job.email_apply_address && (
                <div className="public-email-apply">
                  <h3>Candidater par e-mail</h3>
                  <p>
                    Envoyez votre CV et votre lettre à{" "}
                    <a href={`mailto:${job.email_apply_address}?subject=${encodeURIComponent(`CANDIDATURE ${job.email_reference} - ${job.title}`)}`}>
                      {job.email_apply_address}
                    </a>
                    . La candidature est transmise à l'entreprise avec vos
                    pièces jointes.
                  </p>
                  <p className="small muted">
                    Objet conseillé : CANDIDATURE {job.email_reference} - {job.title}
                  </p>
                  <div className="actions-row">
                    <a
                      className="btn btn-primary btn-small"
                      href={`mailto:${job.email_apply_address}?subject=${encodeURIComponent(`CANDIDATURE ${job.email_reference} - ${job.title}`)}`}
                    >
                      Écrire à OrientSkill AI
                    </a>
                    <Link className="btn btn-outline btn-small" to={`/visuel/${job.id}`}>
                      Voir le visuel LinkedIn
                    </Link>
                  </div>
                </div>
              )}
              {job.source?.url && (
                <a
                  className="btn btn-primary btn-block"
                  href={job.source.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Ouvrir le lien de candidature <ArrowIcon direction="right" size={12} />
                </a>
              )}
              {!job.source?.url && job.email_apply_address && (
                <p className="small muted">
                  Aucun lien externe n'est renseigné : utilisez l'adresse
                  e-mail ci-dessus pour transmettre votre candidature.
                </p>
              )}
            </div>
          ) : done ? (
            <div className="public-done">
              <span className="public-done-icon"><Icon d={I.check} size={20} /></span>
              <h2>Candidature enregistrée</h2>
              <p>
                Votre candidature pour <b>{job.title}</b> est bien enregistrée.
                Votre compte est actif : complétez votre profil pour montrer
                vos compétences et expériences.
              </p>
              <p className="small muted">
                {done.email_sent
                  ? "Vos accès (e-mail et mot de passe provisoire) viennent de vous être envoyés par e-mail."
                  : "Le service e-mail n'est pas configuré : votre session est déjà ouverte, vous pouvez continuer directement. Pensez à changer votre mot de passe dans les paramètres."}
              </p>
              <div className="actions-row">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => navigate("/profil")}
                >
                  Compléter mon profil <ArrowIcon direction="right" size={12} />
                </button>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => navigate("/candidatures")}
                >
                  Voir mes candidatures
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={submit}>
              <h2>Postuler en 30 secondes</h2>
              <p className="small muted">
                Nom, e-mail et téléphone suffisent : votre compte est créé
                automatiquement et votre candidature enregistrée. Vous
                complétez votre profil ensuite, à votre rythme.
              </p>
              <label className="field">
                <span>Nom complet *</span>
                <input
                  value={form.fullName}
                  onChange={(e) => set("fullName", e.target.value)}
                  required
                  minLength={2}
                  placeholder="Ex. Steve Nguema"
                />
              </label>
              <label className="field">
                <span>Adresse e-mail *</span>
                <input
                  type="email"
                  value={form.email}
                  onChange={(e) => set("email", e.target.value)}
                  required
                  placeholder="vous@exemple.cm"
                />
              </label>
              <label className="field">
                <span>Téléphone *</span>
                <input
                  type="tel"
                  value={form.phone}
                  onChange={(e) => set("phone", e.target.value)}
                  required
                  minLength={6}
                  placeholder="+237 6 00 00 00 00"
                />
              </label>
              <label className="field">
                <span>Message au recruteur (facultatif)</span>
                <textarea
                  rows={3}
                  value={form.motivation}
                  onChange={(e) => set("motivation", e.target.value)}
                  maxLength={1000}
                  placeholder="Une phrase sur votre motivation."
                />
              </label>
              <button
                className="btn btn-primary btn-block"
                disabled={busy || !form.fullName.trim() || !form.email.trim() || form.phone.trim().length < 6}
              >
                {busy ? "Envoi…" : "Créer mon compte et postuler"}
              </button>
              <p className="small muted" style={{ marginTop: "0.7rem" }}>
                Déjà inscrit ? <Link to="/login">Connectez-vous</Link> pour
                postuler depuis votre espace. Le téléphone reste privé : les
                recruteurs vous contactent via la messagerie.
              </p>
            </form>
          )}
        </section>
      </main>

      <footer className="public-apply-foot">
        <span>OrientSkill AI · Plateforme d'intelligence professionnelle</span>
      </footer>
    </div>
  );
}
