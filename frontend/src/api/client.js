// Client API : fetch wrapper avec JWT Bearer + gestion 401.
// Le token est stocké dans localStorage (clé orientskill_token, cf. contrat).

const TOKEN_KEY = "orientskill_token";
const USER_KEY = "orientskill_user";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY));
  } catch {
    return null;
  }
}

export function setSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Erreur ${status}`);
    this.status = status;
    this.detail = detail || `Erreur ${status}`;
  }
}

// FastAPI renvoie detail = liste d'objets sur les 422 : on linéarise
// en message lisible pour éviter tout crash de rendu React.
function humanizeDetail(detail) {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = (d?.loc || []).slice(-1)[0];
        const msg = d?.msg || d?.message || "valeur invalide";
        return field ? `${field} : ${msg}` : msg;
      })
      .join(" · ");
  }
  return String(detail);
}

export async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  let payload;
  if (form) {
    payload = form; // FormData : le navigateur définit le Content-Type
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(`/api${path}`, { method, headers, body: payload });

  if (res.status === 401 && !path.startsWith("/auth/")) {
    clearSession();
    window.location.href = "/login";
    throw new ApiError(401, "Session expirée, veuillez vous reconnecter.");
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    throw new ApiError(res.status, humanizeDetail(data?.detail) || `Erreur ${res.status}`);
  }
  return data;
}

// Réponse brute (téléchargements : export de documents).
export async function apiRaw(path) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(`/api${path}`, { headers });
}
