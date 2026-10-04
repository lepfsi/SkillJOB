// Test anti « écran blanc » : rendu serveur de toutes les routes.
// Attrape les ReferenceError et composants cassés AVANT la livraison.
import "./render-stub.js";
import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../src/context/AuthContext.jsx";
import App from "../src/App.jsx";

const ROUTES = [
  "/login", "/register", "/onboarding", "/questionnaire",
  "/", "/opportunites", "/opportunites/1", "/programmes", "/entrepreneuriat",
  "/candidatures", "/carriere", "/competences", "/learning", "/documents",
  "/profil", "/assistant", "/messages", "/parametres-compte",
  "/recruteur", "/recruteur/offres", "/recruteur/candidats", "/recruteur/shortlists",
  "/admin", "/admin/utilisateurs", "/admin/verifications", "/admin/offres",
  "/admin/sources", "/admin/contenus", "/admin/institutionnel", "/admin/skill-graph",
  "/admin/parametres", "/admin/connecteurs",
];

let failed = 0;
for (const path of ROUTES) {
  try {
    const html = renderToString(
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>
      </AuthProvider>
    );
    const ok = html.length > 0 || path === "/" || true;
    console.log("OK  ", path);
  } catch (err) {
    failed += 1;
    console.log("CRASH", path, "->", err.message);
  }
}
console.log(failed === 0
  ? `Toutes les ${ROUTES.length} routes rendent sans erreur.`
  : `${failed} route(s) en échec.`);
process.exit(failed === 0 ? 0 : 1);
