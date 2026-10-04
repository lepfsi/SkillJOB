// Petits éléments d'interface réutilisables.

export function Loader({ label = "Chargement…" }) {
  return <p className="muted loader">{label}</p>;
}

export function ErrorNote({ error }) {
  if (!error) return null;
  return <div className="alert alert-error">{String(error)}</div>;
}

export function Empty({ title, children }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {children}
    </div>
  );
}

export function Section({ title, children, aside }) {
  return (
    <section className="section">
      <div className="section-head">
        <h2>{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}
