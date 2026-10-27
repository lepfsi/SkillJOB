// Badge de vérification partagé : un sceau sobre (bouclier + coche),
// décliné en icône seule ou en pastille avec libellé. Il remplace les
// cercles bleus et les pastilles disparates pour un rendu cohérent.
export default function VerifiedBadge({ label = "", size = 18, className = "" }) {
  const classes = [
    "verified-badge",
    label ? "is-labeled" : "",
    className,
  ].filter(Boolean).join(" ");

  return (
    <span
      className={classes}
      title="Profil vérifié"
      aria-label="Profil vérifié"
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        aria-hidden="true"
        focusable="false"
      >
        <path
          d="M12 2.2 20 5.7v6.1c0 4.7-3.2 8.3-8 9.9-4.8-1.6-8-5.2-8-9.9V5.7L12 2.2Z"
          fill="currentColor"
        />
        <path
          d="m8.1 12.1 2.5 2.5 5.4-5.5"
          fill="none"
          stroke="#fff"
          strokeWidth="2.1"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {label && <span className="verified-badge-label">{label}</span>}
    </span>
  );
}
