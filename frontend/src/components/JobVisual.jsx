import { useEffect, useState } from "react";
import { Icon, I } from "./icons.jsx";
import CompanyLogo from "./CompanyLogo.jsx";
import { useDomains } from "./DomainPicker.jsx";

// Visuel d'offre partagé : la photo déposée si elle existe, sinon une tuile
// illustrée par domaine. Le repli couvre aussi les photos perdues après un
// redéploiement (stockage local éphémère) : on ne montre jamais d'image cassée.

const TONES = [
  { test: /informatique|numérique|numerique|digital|tech|logiciel|data/i, tone: "tech", icon: I.zap },
  { test: /santé|sante|soin|médical|medical|pharma/i, tone: "health", icon: I.shield },
  { test: /finance|banque|comptab|assurance|audit/i, tone: "finance", icon: I.chart },
  { test: /éducation|education|formation|enseignement|école|ecole/i, tone: "education", icon: I.book },
  { test: /bâtiment|batiment|construction|industrie|mécanique|mecanique|énergie|energie/i, tone: "industry", icon: I.layers },
  { test: /commerce|vente|marketing|communication|clientèle|clientele/i, tone: "commerce", icon: I.trending },
  { test: /ong|international|humanitaire|social|association/i, tone: "social", icon: I.globe },
  { test: /transport|logistique|supply|achat/i, tone: "logistics", icon: I.send },
  { test: /agriculture|agro|environnement|forêt|foret/i, tone: "agri", icon: I.sun },
  { test: /droit|justice|administration|public|juridique/i, tone: "public", icon: I.landmark },
];

function toneFor(label) {
  return TONES.find(({ test }) => test.test(label || "")) || {
    tone: "default",
    icon: I.briefcase,
  };
}

export default function JobVisual({
  job,
  domains: providedDomains,
  variant = "row",
  className = "",
}) {
  const [failed, setFailed] = useState(false);
  const { domains: fetchedDomains } = useDomains();
  const domains = providedDomains || fetchedDomains;

  useEffect(() => {
    setFailed(false);
  }, [job?.photo_url]);

  const domain = domains.find((row) => String(row.id) === String(job?.domain_id));
  const label = domain?.name || job?.sector || "Opportunité";
  const company = job?.company || job?.company_branding?.name || "";
  const { tone, icon } = toneFor(label);
  const base = `job-visual job-visual-${variant} ${className}`.trim();

  if (job?.photo_url && !failed) {
    return (
      <span className={`${base} job-visual-photo`}>
        <img
          src={job.photo_url}
          alt=""
          loading="lazy"
          onError={() => setFailed(true)}
        />
      </span>
    );
  }

  const iconSize = variant === "banner" ? 30 : variant === "thumb" ? 20 : 19;

  return (
    <span className={`${base} job-visual-${tone}`} aria-hidden="true">
      <span className="job-visual-glow" />
      <span className="job-visual-icon">
        <Icon d={icon} size={iconSize} />
      </span>
      {variant === "banner" && (
        <span className="job-visual-copy">
          <span className="job-visual-domain">{label}</span>
          <span className="job-visual-title">{job?.title || "Offre à pourvoir"}</span>
          <span className="job-visual-meta">
            {[company, job?.location, job?.contract_type]
              .filter(Boolean)
              .join(" · ")}
          </span>
        </span>
      )}
      <CompanyLogo
        name={company}
        logoUrl={job?.company_branding?.logo_url}
        className="job-visual-initials"
      />
    </span>
  );
}
