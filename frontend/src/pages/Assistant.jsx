import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { api } from "../api/client.js";
import AssistantChat from "../components/AssistantChat.jsx";

// Assistant conversationnel (tous les rôles). Le chat lui-même vit dans
// components/AssistantChat.jsx, partagé avec la page « Mon agent ».
// Le paramètre ?q= permet d'arriver avec une question prête à envoyer
// (ex. depuis une offre : « Adapte mon CV pour cette offre »).

export default function Assistant() {
  const { user } = useAuth();
  const [engine, setEngine] = useState(null); // {mode, model, llm_enabled}
  const [searchParams] = useSearchParams();

  useEffect(() => {
    if (user?.role === "admin") {
      api("/assistant/status").then(setEngine).catch(() => {});
    }
  }, [user?.role]);

  return (
    <div className="page page-narrow">
      <h1>Assistant</h1>
      <p className="page-lead">
        {user?.role === "recruiter"
          ? "Ton assistant recrutement : structure tes offres, cherche des talents, suit les candidatures reçues."
          : "Discute naturellement avec Ori. Il s'appuie sur tes données, peut fouiller le web, et agit avec toi : CV, lettre, entretien, profil."}
      </p>

      {engine && user?.role === "admin" && (
        engine.llm_enabled ? (
          <div className="alert alert-info" style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <span className="badge badge-strong">Modèle connecté</span>
            <span className="small">Ori fonctionne avec ton modèle : <strong>{engine.model || "OpenAI-compatible"}</strong></span>
          </div>
        ) : (
          <div className="alert alert-error" style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
            <span className="badge badge-weak">Mode local</span>
            <span className="small">
              Aucun modèle IA configuré : Ori utilise le moteur de règles local
              (rapide mais limité).
              {" "}
              <Link to="/admin/parametres">Configurer le modèle → Paramètres · LLM</Link>
            </span>
          </div>
        )
      )}

      <AssistantChat
        initialMessage={searchParams.get("q") || null}
        pageContext={searchParams.get("page") || null}
      />
    </div>
  );
}
