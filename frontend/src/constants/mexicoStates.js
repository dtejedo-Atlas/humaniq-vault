/**
 * Estados de México para dropdown de ubicación
 */
export const MEXICO_STATES = [
  { value: 'AGS', label: 'Aguascalientes' },
  { value: 'BC', label: 'Baja California' },
  { value: 'BCS', label: 'Baja California Sur' },
  { value: 'CAM', label: 'Campeche' },
  { value: 'CHIS', label: 'Chiapas' },
  { value: 'CHIH', label: 'Chihuahua' },
  { value: 'CDMX', label: 'Ciudad de México' },
  { value: 'COAH', label: 'Coahuila' },
  { value: 'COL', label: 'Colima' },
  { value: 'DGO', label: 'Durango' },
  { value: 'GTO', label: 'Guanajuato' },
  { value: 'GRO', label: 'Guerrero' },
  { value: 'HGO', label: 'Hidalgo' },
  { value: 'JAL', label: 'Jalisco' },
  { value: 'MEX', label: 'Estado de México' },
  { value: 'MICH', label: 'Michoacán' },
  { value: 'MOR', label: 'Morelos' },
  { value: 'NAY', label: 'Nayarit' },
  { value: 'NL', label: 'Nuevo León' },
  { value: 'OAX', label: 'Oaxaca' },
  { value: 'PUE', label: 'Puebla' },
  { value: 'QRO', label: 'Querétaro' },
  { value: 'QROO', label: 'Quintana Roo' },
  { value: 'SLP', label: 'San Luis Potosí' },
  { value: 'SIN', label: 'Sinaloa' },
  { value: 'SON', label: 'Sonora' },
  { value: 'TAB', label: 'Tabasco' },
  { value: 'TAM', label: 'Tamaulipas' },
  { value: 'TLAX', label: 'Tlaxcala' },
  { value: 'VER', label: 'Veracruz' },
  { value: 'YUC', label: 'Yucatán' },
  { value: 'ZAC', label: 'Zacatecas' },
];

export const COUNTRIES = [
  { value: 'México', label: 'México' },
  { value: 'Estados Unidos', label: 'Estados Unidos' },
  { value: 'Canadá', label: 'Canadá' },
  { value: 'España', label: 'España' },
  { value: 'Colombia', label: 'Colombia' },
  { value: 'Argentina', label: 'Argentina' },
  { value: 'Chile', label: 'Chile' },
  { value: 'Perú', label: 'Perú' },
  { value: 'Brasil', label: 'Brasil' },
  { value: 'Otro', label: 'Otro' },
];

export const WORK_SCHEMES = [
  { value: 'on_site', label: 'Presencial', icon: 'Building2' },
  { value: 'hybrid', label: 'Híbrido', icon: 'Building' },
  { value: 'remote', label: 'Remoto', icon: 'Home' },
];

export const SENIORITY_OPTIONS = [
  { value: 'trainee', label: 'Becario / Trainee' },
  { value: 'entry', label: 'Entry Level' },
  { value: 'junior', label: 'Junior / Coordinador' },
  { value: 'mid', label: 'Mid Level / Especialista' },
  { value: 'senior', label: 'Senior' },
  { value: 'lead', label: 'Lead / Líder' },
  { value: 'manager', label: 'Gerente / Manager' },
  { value: 'director', label: 'Director' },
  { value: 'vp', label: 'VP / Vicepresidente' },
  { value: 'c_level', label: 'C-Level (CEO, CFO, COO, etc.)' },
];

export const getStateLabel = (stateCode) => {
  const state = MEXICO_STATES.find(s => s.value === stateCode);
  return state ? state.label : stateCode;
};

export const getWorkSchemeLabel = (scheme) => {
  const ws = WORK_SCHEMES.find(w => w.value === scheme);
  return ws ? ws.label : scheme;
};

export const getSeniorityLabel = (seniority) => {
  const s = SENIORITY_OPTIONS.find(opt => opt.value === seniority);
  return s ? s.label : seniority;
};
