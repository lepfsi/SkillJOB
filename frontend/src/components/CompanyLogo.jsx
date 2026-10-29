import { useEffect, useState } from "react";
import { resourceHref } from "../api/client.js";
import { initialsOf } from "../lib.js";

// Identité visuelle partagée d'une entreprise : le logo public si le
// recruteur en a déposé un, sinon les initiales. Le repli couvre aussi une
// image perdue après un redéploiement : on ne montre jamais d'image cassée.
export default function CompanyLogo({
  name,
  logoUrl,
  className = "company-logo",
  style,
  title,
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setFailed(false);
  }, [logoUrl]);

  const classes = className.split(/\s+/).includes("company-logo")
    ? className
    : `${className} company-logo`;

  if (!logoUrl || failed) {
    return (
      <span className={classes} style={style} title={title} aria-hidden="true">
        {initialsOf(name)}
      </span>
    );
  }
  return (
    <span className={classes} style={style} title={title} aria-hidden="true">
      <img
        src={resourceHref(logoUrl)}
        alt=""
        loading="lazy"
        decoding="async"
        onError={() => setFailed(true)}
      />
    </span>
  );
}
