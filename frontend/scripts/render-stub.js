// Stubs navigateur pour le rendu serveur (exécutés avant le reste)
globalThis.localStorage = {
  getItem: () => null, setItem: () => {}, removeItem: () => {}, clear: () => {},
};
globalThis.fetch = () => Promise.reject(new Error("no fetch in SSR test"));
globalThis.window = { location: { href: "" }, scrollTo: () => {}, addEventListener: () => {} };
