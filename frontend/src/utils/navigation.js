// Origen de navegación hacia la ficha de candidato: permite "Volver" exacto sin recalcular.
export const buildOrigin = (location, label) => ({
  from: `${location.pathname}${location.search || ''}`,
  label,
  scrollY: typeof window !== 'undefined' ? window.scrollY : 0,
});

export const openCandidate = (navigate, location, candidateId, label = 'lista') => {
  navigate(`/candidates/${candidateId}`, { state: { origin: buildOrigin(location, label) } });
};

export const backTarget = (location) => {
  const origin = location?.state?.origin;
  if (origin?.from) return { to: origin.from, label: origin.label, scrollY: origin.scrollY, restore: true };
  return { to: '/candidates', label: 'Candidatos', scrollY: 0, restore: false };
};

const KEY = (pathname) => `view-state:${pathname}`;

export const saveViewState = (pathname, state) => {
  try {
    sessionStorage.setItem(KEY(pathname), JSON.stringify({ ...state, savedAt: Date.now() }));
  } catch (_) { /* almacenamiento no disponible */ }
};

export const loadViewState = (pathname) => {
  try {
    const raw = sessionStorage.getItem(KEY(pathname));
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
};

export const restoreScroll = (y) => {
  if (!y) return;
  requestAnimationFrame(() => window.scrollTo({ top: y, behavior: 'instant' }));
};
