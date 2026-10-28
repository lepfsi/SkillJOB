// Utilitaires partagés : formats FR, libellés, sanitisation, mini-markdown.

export function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
}

export function fmtDateTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function relTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (days <= 0) return "Aujourd'hui";
  if (days === 1) return "Hier";
  if (days < 7) return `Il y a ${days} jours`;
  return fmtDate(iso);
}

// Seuils alignés sur le backend (matching.py) : forte >= 75, moyenne >= 45.
export function scoreLevel(score) {  if (score == null) return null;
  if (score >= 75) return "forte";
  if (score >= 45) return "moyenne";
  return "faible";
}

export const LEVEL_LABELS = { forte: "Forte", moyenne: "Moyenne", faible: "Faible" };

// Initiales d'un nom (logo d'entreprise, avatar) : « Express Union » -> « EU ».
export function initialsOf(name) {
  return (name || "?")
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

// Accord singulier / pluriel simple : plural(3, "", "s") -> "s".
export function plural(n, one, many) {
  return n > 1 ? many : one;
}

export const STATUS_ORDER = [
  "identifiee", "cv_prepare", "envoyee", "en_attente",
  "entretien", "offre", "acceptee", "refusee", "retiree", "declinee",
];

export const STATUS_LABELS = {
  identifiee: "Identifiée",
  cv_prepare: "CV préparé",
  envoyee: "Envoyée",
  en_attente: "En attente",
  entretien: "Entretien",
  offre: "Offre reçue",
  acceptee: "Acceptée",
  refusee: "Refusée",
  retiree: "Retirée",
  declinee: "Déclinée",
};

export const CLOSED_STATUSES = new Set([
  "acceptee", "refusee", "retiree", "declinee",
]);

export function statusTone(status) {
  if (status === "acceptee") return "ok";
  if (status === "refusee" || status === "retiree") return "ko";
  if (status === "declinee") return "wait";
  if (status === "entretien" || status === "offre") return "focus";
  if (status === "en_attente") return "wait";
  return "open";
}

// Transitions réellement autorisées au recruteur. Le candidat garde la
// main sur l'envoi, l'acceptation et le retrait ; le recruteur instruit.
export const RECRUITER_NEXT = {
  envoyee: "en_attente",
  en_attente: "entretien",
  entretien: "offre",
};

export const REFUSABLE_STATUSES = new Set([
  "envoyee", "en_attente", "entretien", "offre",
]);

export const EXPERIENCE_TYPE_LABELS = {
  formal: "Emploi formel",
  informal: "Expérience informelle",
  freelance: "Freelance / missions",
  volunteer: "Bénévolat / associatif",
  apprenticeship: "Apprentissage / stage",
  project: "Projet personnel",
};

export const PROFICIENCY_LABELS = {
  debutant: "Débutant",
  intermediaire: "Intermédiaire",
  avance: "Avancé",
};

export const SOURCE_LABELS = {
  declared: "Déclarée",
  inferred: "Détectée",
  evidence: "Avec preuves",
};

// Natures de preuve d'une compétence (profil + formations vérifiées).
export const EVIDENCE_KIND_LABELS = {
  experience: "Expérience",
  project: "Projet",
  certification: "Certification",
  education: "Formation",
};

export const ACCESSIBILITY_LABELS = {
  immediate: "Accessible immédiatement",
  with_upskilling: "Après montée en compétences",
  long_term: "Trajectoire long terme",
};

export const RESOURCE_TYPE_LABELS = {
  course: "Cours",
  certification: "Certification",
  project: "Projet pratique",
  free: "Ressource gratuite",
};

export const CONTRACT_TYPES = ["CDI", "CDD", "Stage", "Freelance", "Apprentissage"];

// Modèles de documents (cf. GET /api/cv-templates et /api/letter-templates).
// Ces libellés servent de repli : les noms officiels viennent du catalogue.
export const CV_TEMPLATE_LABELS = {
  classique: "Classique",
  ats: "ATS (robots de recrutement)",
  moderne: "Moderne",
  deux_colonnes: "Deux colonnes",
  elegant: "Élégant",
  compact: "Compact (1 page)",
};

export const LETTER_TEMPLATE_LABELS = {
  classique: "Classique",
  moderne: "Moderne",
  email: "Courriel",
};

// Couleurs d'accent au choix du candidat (stockées sur le document).
// « hex » = accent vif affiché dans les pastilles (cf. familles cv_pdf).
// Un modèle garde sa couleur propre tant que le candidat n'en choisit pas ;
// le modèle ATS suit aussi une couleur explicitement choisie.
export const ACCENTS = [
  { key: "vert", label: "Vert", hex: "#2FB37A" },
  { key: "bleu", label: "Bleu", hex: "#3AA6E0" },
  { key: "orange", label: "Orange", hex: "#F0932B" },
  { key: "bordeaux", label: "Bordeaux", hex: "#C2475D" },
  { key: "ardoise", label: "Ardoise", hex: "#7FA3B5" },
  { key: "violet", label: "Violet", hex: "#7C5CE0" },
  { key: "turquoise", label: "Turquoise", hex: "#22B8B0" },
  { key: "rouge", label: "Rouge", hex: "#D9534F" },
  { key: "rose", label: "Rose", hex: "#D66A9A" },
  { key: "indigo", label: "Indigo", hex: "#4C5FD5" },
  { key: "ambre", label: "Ambre", hex: "#D9A21B" },
  { key: "menthe", label: "Menthe", hex: "#3FBF8F" },
  { key: "brun", label: "Brun", hex: "#8B5E3C" },
];

export function accentHex(key) {
  if (key && /^#[0-9a-fA-F]{6}$/.test(key)) return key;
  return ACCENTS.find((a) => a.key === key)?.hex || null;
}

export function accentLabel(key) {
  if (!key) return "";
  if (/^#[0-9a-fA-F]{6}$/.test(key)) return `Personnalisée (${key.toUpperCase()})`;
  return ACCENTS.find((a) => a.key === key)?.label || key;
}

// Accent par défaut de chaque modèle quand le candidat n'en choisit pas
// (miroir de cv_builder.DEFAULT_ACCENTS côté backend).
export const DEFAULT_ACCENT_BY_TEMPLATE = {
  classique: "vert",
  ats: null,
  moderne: "orange",
  deux_colonnes: "vert",
  elegant: "bordeaux",
  compact: "bleu",
};

// Couleur de repli quand le modèle n'a pas d'accent nommé par défaut.
export const DEFAULT_ACCENT_HEX_BY_TEMPLATE = {
  ats: "#2BD9C5",
};

export function templateAccentHex(templateId, accentKey) {
  if (accentKey && /^#[0-9a-fA-F]{6}$/.test(accentKey)) return accentKey;
  const key = accentKey || DEFAULT_ACCENT_BY_TEMPLATE[templateId];
  return accentHex(key) || DEFAULT_ACCENT_HEX_BY_TEMPLATE[templateId] || null;
}

export const INSTITUTION_LABELS = {
  minfopra: "MINFOPRA · Fonction publique et réforme administrative",
  minesup: "MINESUP · Enseignement supérieur",
  minefop: "MINEFOP · Emploi et formation professionnelle",
  ong: "ONG et organisations internationales",
  mindef: "MINDEF · Défense",
  dgsn: "DGSN · Sûreté nationale (police)",
  appels_projets: "Appels à projets des ministères",
};

export const ENTREPRENEUR_KIND_LABELS = {
  concours: "Concours et appels à projets",
  accompagnement: "Accompagnement et incubation",
  financement: "Financement",
  formation: "Formation entrepreneuriale",
};

export const VERIFICATION_LABELS = {
  none: "Non vérifié",
  pending: "Vérification en cours",
  verified: "Profil vérifié",
  rejected: "Document non retenu",
};

// Traduit les liens internes renvoyés par l'assistant (chemins API backend)
// vers les routes du frontend.
export function mapInternalPath(href) {
  if (!href) return "/";
  const map = {
    "/profile": "/profil",
    "/careers": "/carriere",
    "/market": "/carriere",
    "/dashboard": "/",
    "/learning": "/learning",
    "/documents": "/documents",
    "/jobs": "/opportunites",
    "/applications": "/candidatures",
    "/entrepreneurship": "/entrepreneuriat",
  };
  if (map[href]) return map[href];
  if (href.startsWith("/entrepreneurship#")) return `/entrepreneuriat${href.slice("/entrepreneurship".length)}`;
  if (href.startsWith("/jobs/")) return `/opportunites/${href.slice("/jobs/".length)}`;
  return href;
}

const str = (v) => (v == null ? "" : String(v).trim());
const intOrNull = (v) => {
  if (v === "" || v == null) return null;
  const n = parseInt(v, 10);
  return Number.isNaN(n) ? null : n;
};

// Nettoie le profil avant PUT /api/profile (années -> int ou null, champs vides).
export function sanitizeProfile(p) {
  if (!p) return p;
  return {
    title: str(p.title) || null,
    summary: str(p.summary),
    location: str(p.location) || null,
    mobility: str(p.mobility) || null,
    availability: str(p.availability) || null,
    education: (p.education || [])
      .map((e) => ({
        degree: str(e.degree),
        institution: str(e.institution),
        field: str(e.field),
        start_year: intOrNull(e.start_year),
        end_year: intOrNull(e.end_year),
      }))
      .filter((e) => e.degree || e.institution || e.field),
    experiences: (p.experiences || [])
      .map((e) => ({
        id: e.id || null,
        title: str(e.title),
        organization: str(e.organization),
        type: EXPERIENCE_TYPE_LABELS[e.type] ? e.type : "formal",
        description: str(e.description),
        start_date: str(e.start_date) || null,
        end_date: str(e.end_date) || null,
        skills: (e.skills || []).map(str).filter(Boolean),
      }))
      .filter((e) => e.title || e.description),
    certifications: (p.certifications || [])
      .map((c) => ({ name: str(c.name), issuer: str(c.issuer), year: intOrNull(c.year) }))
      .filter((c) => c.name),
    languages: (p.languages || [])
      .map((l) => ({ language: str(l.language), level: str(l.level) }))
      .filter((l) => l.language),
    projects: (p.projects || [])
      .map((x) => ({ name: str(x.name), description: str(x.description), url: str(x.url) || null, skills: (x.skills || []).map(str).filter(Boolean) }))
      .filter((x) => x.name || x.description),
    skills: (p.skills || [])
      .map((s) => ({
        skill: str(s.skill),
        category: str(s.category),
        proficiency: ["debutant", "intermediaire", "avance"].includes(s.proficiency) ? s.proficiency : "intermediaire",
        source: ["declared", "inferred", "evidence"].includes(s.source) ? s.source : "declared",
        evidence_count: Number(s.evidence_count) || 0,
      }))
      .filter((s) => s.skill),
    preferences: {
      domain_id: intOrNull(p.preferences?.domain_id),
      specialty_ids: (p.preferences?.specialty_ids || [])
        .map((id) => intOrNull(id))
        .filter((id) => id != null),
      domain_other: str(p.preferences?.domain_other),
      sectors: (p.preferences?.sectors || []).map(str).filter(Boolean),
      target_roles: (p.preferences?.target_roles || []).map(str).filter(Boolean),
      contract_types: (p.preferences?.contract_types || []).map(str).filter(Boolean),
      remote_ok: !!p.preferences?.remote_ok,
      linkedin_url: str(p.preferences?.linkedin_url) || null,
    },
  };
}

export function escapeHtml(s) {
  // Entités HTML construites via unicode pour échapper tout caractère spécial.
  const AMP = "\u0026amp;";
  const LT = "\u0026lt;";
  const GT = "\u0026gt;";
  const QUOT = "\u0026quot;";
  return String(s)
    .replace(/&/g, AMP)
    .replace(/</g, LT)
    .replace(/>/g, GT)
    .replace(/"/g, QUOT);
}

// Mini-rendu markdown (titres, listes, gras, italique, liens) pour les
// documents ET le chat de l'assistant. Le texte est d'abord échappé :
// seul le markdown généré devient du HTML sûr.
export function mdToHtml(md) {
  if (!md) return "";
  const inline = (t) => {
    let out = t
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
    // Liens markdown : [texte](https://…) : uniquement http(s)
    out = out.replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noreferrer">$1</a>'
    );
    return out;
  };
  const out = [];
  let list = null;
  const flush = () => {
    if (list) {
      out.push(`<ul>${list.join("")}</ul>`);
      list = null;
    }
  };
  for (const raw of String(md).split("\n")) {
    const line = raw.trim();
    if (!line) {
      flush();
      continue;
    }
    if (line.startsWith("### ")) {
      flush();
      out.push(`<h3>${inline(line.slice(4))}</h3>`);
    } else if (line.startsWith("## ")) {
      flush();
      out.push(`<h2>${inline(line.slice(3))}</h2>`);
    } else if (line.startsWith("# ")) {
      flush();
      out.push(`<h1>${inline(line.slice(2))}</h1>`);
    } else if (line.startsWith("- ") || line.startsWith("• ")) {
      (list = list || []).push(`<li>${inline(line.slice(2))}</li>`);
    } else {
      flush();
      out.push(`<p>${inline(line)}</p>`);
    }
  }
  flush();
  return out.join("");
}
