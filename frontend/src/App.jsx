import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import { useAuth } from "./context/AuthContext.jsx";

import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import Onboarding from "./pages/Onboarding.jsx";
import Questionnaire from "./pages/Questionnaire.jsx";
import DraftReview from "./pages/DraftReview.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Inbox from "./pages/Inbox.jsx";
import Opportunities from "./pages/Opportunities.jsx";
import OpportunityDetail from "./pages/OpportunityDetail.jsx";
import Applications from "./pages/Applications.jsx";
import Career from "./pages/Career.jsx";
import Skills from "./pages/Skills.jsx";
import Learning from "./pages/Learning.jsx";
import Documents from "./pages/Documents.jsx";
import Profile from "./pages/Profile.jsx";
import Assistant from "./pages/Assistant.jsx";
import Messages from "./pages/Messages.jsx";
import Institutional from "./pages/Institutional.jsx";
import Entrepreneurship from "./pages/Entrepreneurship.jsx";
import AccountSettings from "./pages/AccountSettings.jsx";

import AdminHome from "./pages/admin/AdminHome.jsx";
import AdminSettings from "./pages/admin/AdminSettings.jsx";
import AdminConnecteurs from "./pages/admin/AdminConnecteurs.jsx";
import AdminJobs from "./pages/admin/AdminJobs.jsx";
import AdminUsers from "./pages/admin/AdminUsers.jsx";
import AdminVerifications from "./pages/admin/AdminVerifications.jsx";
import AdminSources from "./pages/admin/AdminSources.jsx";
import AdminPublicContent from "./pages/admin/AdminPublicContent.jsx";
import AdminInstitutional from "./pages/admin/AdminInstitutional.jsx";
import AdminSkillGraph from "./pages/admin/AdminSkillGraph.jsx";

import RecruiterHome from "./pages/recruiter/RecruiterHome.jsx";
import RecruiterJobs from "./pages/recruiter/RecruiterJobs.jsx";
import RecruiterCandidates from "./pages/recruiter/RecruiterCandidates.jsx";
import RecruiterShortlists from "./pages/recruiter/RecruiterShortlists.jsx";

// Cloisonnement des rôles : chaque rôle voit UNIQUEMENT ses pages.
// - candidat : parcours talent complet ;
// - recruteur : espace entreprise + messagerie + paramètres ;
// - admin : console d'administration + messagerie + paramètres.

function homeFor(role) {
  if (role === "admin") return "/admin";
  if (role === "recruiter") return "/recruteur";
  return "/";
}

function RequireCandidate({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "candidate") return <Navigate to={homeFor(user.role)} replace />;
  return <Layout>{children}</Layout>;
}

function RequireRecruiter({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "recruiter") return <Navigate to={homeFor(user.role)} replace />;
  return <Layout>{children}</Layout>;
}

function RequireAdmin({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin") return <Navigate to={homeFor(user.role)} replace />;
  return <Layout>{children}</Layout>;
}

// Pages accessibles à TOUS les rôles authentifiés (messagerie interne,
// paramètres du compte).
function RequireAny({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* -------------------- Espace candidat -------------------- */}
      <Route path="/" element={<RequireCandidate><Dashboard /></RequireCandidate>} />
      <Route path="/inbox" element={<RequireCandidate><Inbox /></RequireCandidate>} />
      <Route path="/opportunites" element={<RequireCandidate><Opportunities /></RequireCandidate>} />
      <Route path="/opportunites/:id" element={<RequireCandidate><OpportunityDetail /></RequireCandidate>} />
      <Route path="/programmes" element={<RequireCandidate><Institutional /></RequireCandidate>} />
      <Route path="/entrepreneuriat" element={<RequireCandidate><Entrepreneurship /></RequireCandidate>} />
      <Route path="/candidatures" element={<RequireCandidate><Applications /></RequireCandidate>} />
      <Route path="/carriere" element={<RequireCandidate><Career /></RequireCandidate>} />
      <Route path="/competences" element={<RequireCandidate><Skills /></RequireCandidate>} />
      <Route path="/learning" element={<RequireCandidate><Learning /></RequireCandidate>} />
      <Route path="/documents" element={<RequireCandidate><Documents /></RequireCandidate>} />
      <Route path="/profil" element={<RequireCandidate><Profile /></RequireCandidate>} />
      <Route path="/assistant" element={<RequireAny><Assistant /></RequireAny>} />
      <Route path="/onboarding" element={<RequireCandidate><Onboarding /></RequireCandidate>} />
      <Route path="/questionnaire" element={<RequireCandidate><Questionnaire /></RequireCandidate>} />
      <Route path="/validation-profil" element={<RequireCandidate><DraftReview /></RequireCandidate>} />

      {/* -------------------- Espace recruteur -------------------- */}
      <Route path="/recruteur" element={<RequireRecruiter><RecruiterHome /></RequireRecruiter>} />
      <Route path="/recruteur/offres" element={<RequireRecruiter><RecruiterJobs /></RequireRecruiter>} />
      <Route path="/recruteur/candidats" element={<RequireRecruiter><RecruiterCandidates /></RequireRecruiter>} />
      <Route path="/recruteur/candidats/:candidateId" element={<RequireRecruiter><RecruiterCandidates /></RequireRecruiter>} />
      <Route path="/recruteur/shortlists" element={<RequireRecruiter><RecruiterShortlists /></RequireRecruiter>} />

      {/* -------------------- Console admin -------------------- */}
      <Route path="/admin" element={<RequireAdmin><AdminHome /></RequireAdmin>} />
      <Route path="/admin/utilisateurs" element={<RequireAdmin><AdminUsers /></RequireAdmin>} />
      <Route path="/admin/verifications" element={<RequireAdmin><AdminVerifications /></RequireAdmin>} />
      <Route path="/admin/offres" element={<RequireAdmin><AdminJobs /></RequireAdmin>} />
      <Route path="/admin/sources" element={<RequireAdmin><AdminSources /></RequireAdmin>} />
      <Route path="/admin/contenus" element={<RequireAdmin><AdminPublicContent /></RequireAdmin>} />
      <Route path="/admin/institutionnel" element={<RequireAdmin><AdminInstitutional /></RequireAdmin>} />
      <Route path="/admin/skill-graph" element={<RequireAdmin><AdminSkillGraph /></RequireAdmin>} />
      <Route path="/admin/parametres" element={<RequireAdmin><AdminSettings /></RequireAdmin>} />
      <Route path="/admin/connecteurs" element={<RequireAdmin><AdminConnecteurs /></RequireAdmin>} />

      {/* -------------------- Rôles neutres -------------------- */}
      <Route path="/messages" element={<RequireAny><Messages /></RequireAny>} />
      <Route path="/messages/:otherId" element={<RequireAny><Messages /></RequireAny>} />
      <Route path="/parametres-compte" element={<RequireAny><AccountSettings /></RequireAny>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
