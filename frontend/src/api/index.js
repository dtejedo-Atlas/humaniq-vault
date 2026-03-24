import axios from 'axios';

const API_BASE = process.env.REACT_APP_BACKEND_URL + '/api';

// Candidates
export const candidatesAPI = {
  getAll: (params = {}) => axios.get(`${API_BASE}/candidates`, { params }),
  getById: (id) => axios.get(`${API_BASE}/candidates/${id}`),
  create: (data) => axios.post(`${API_BASE}/candidates`, data),
  update: (id, data) => axios.put(`${API_BASE}/candidates/${id}`, data),
  addNote: (id, note) => {
    const formData = new FormData();
    formData.append('note_text', note);
    return axios.post(`${API_BASE}/candidates/${id}/notes`, formData);
  },
  uploadResume: (file, candidateId = null) => {
    const formData = new FormData();
    formData.append('file', file);
    if (candidateId) {
      formData.append('candidate_id', candidateId);
    }
    return axios.post(`${API_BASE}/candidates/upload-resume`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  },
  getDuplicates: (id) => axios.get(`${API_BASE}/candidates/${id}/duplicates`),
  dismissDuplicate: (candidateId, suggestionId) => 
    axios.post(`${API_BASE}/candidates/${candidateId}/dismiss-duplicate/${suggestionId}`)
};

// Atlas AI
export const atlasAPI = {
  classify: (candidateId) => axios.post(`${API_BASE}/atlas/classify/${candidateId}`),
  approveClassification: (candidateId) => axios.post(`${API_BASE}/atlas/approve-classification/${candidateId}`)
};

// Search
export const searchAPI = {
  hybrid: (params) => axios.post(`${API_BASE}/search/hybrid`, null, { params }),
  save: (name, query, filters, use_semantic) => {
    const formData = new FormData();
    formData.append('name', name);
    if (query) formData.append('query', query);
    formData.append('filters', JSON.stringify(filters));
    formData.append('use_semantic', use_semantic);
    return axios.post(`${API_BASE}/search/save`, formData);
  },
  getSaved: () => axios.get(`${API_BASE}/search/saved`)
};

// Dashboard
export const dashboardAPI = {
  getStats: () => axios.get(`${API_BASE}/dashboard/stats`),
  getRecentActivity: (limit = 10) => axios.get(`${API_BASE}/dashboard/recent-activity`, { params: { limit } })
};

// Taxonomy
export const taxonomyAPI = {
  getIndustries: () => axios.get(`${API_BASE}/taxonomy/industries`),
  getFunctionalAreas: () => axios.get(`${API_BASE}/taxonomy/functional-areas`),
  createIndustry: (data) => axios.post(`${API_BASE}/admin/industries`, data),
  updateIndustry: (id, data) => axios.put(`${API_BASE}/admin/industries/${id}`, data),
  deleteIndustry: (id) => axios.delete(`${API_BASE}/admin/industries/${id}`),
  createFunctionalArea: (data) => axios.post(`${API_BASE}/admin/functional-areas`, data),
  updateFunctionalArea: (id, data) => axios.put(`${API_BASE}/admin/functional-areas/${id}`, data),
  deleteFunctionalArea: (id) => axios.delete(`${API_BASE}/admin/functional-areas/${id}`)
};

// Seed
export const seedAPI = {
  initializeData: () => axios.post(`${API_BASE}/seed/initial-data`)
};

export default {
  candidatesAPI,
  atlasAPI,
  searchAPI,
  dashboardAPI,
  taxonomyAPI,
  seedAPI
};