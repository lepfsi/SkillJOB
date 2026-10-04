import { createContext, useContext, useState } from "react";
import { api, setSession, clearSession, getUser, getToken } from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => (getToken() ? getUser() : null));

  async function login(email, password) {
    const res = await api("/auth/login", { method: "POST", body: { email, password } });
    setSession(res.token, res.user);
    setUser(res.user);
    return res.user;
  }

  async function register(payload) {
    // Inscription recruteur : endpoint dédié (type entreprise / cabinet /
    // indépendant). Sinon : endpoint candidat.
    const isRecruiter = !!(payload.recruiter_type || payload.company_name);
    const res = await api(
      isRecruiter ? "/auth/register/recruiter" : "/auth/register",
      { method: "POST", body: payload }
    );
    setSession(res.token, res.user);
    setUser(res.user);
    return res.user;
  }

  function logout() {
    clearSession();
    setUser(null);
  }

  async function refreshUser() {
    // Resynchronise l'utilisateur courant depuis le serveur (MFA,
    // vérification, photo… mettent à jour ces champs).
    const fresh = await api("/auth/me");
    setUser(fresh);
    localStorage.setItem("orientskill_user", JSON.stringify(fresh));
    return fresh;
  }

  return (
    <AuthContext.Provider value={{ user, setUser, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
