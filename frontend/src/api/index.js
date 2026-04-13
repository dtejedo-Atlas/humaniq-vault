import axios from 'axios';

const API_BASE = process.env.REACT_APP_BACKEND_URL + '/api';

// Candidates
export const candidatesAPI = {
  getAll: (params = {}) => axios.get(`${API_BASE}/candidates`, { params }),
  getById: (id) => axios.get(`${API_BASE}/candidates/${id}`),
  create: (data) => axios.post(`${API_BASE}/candidates`, data),
  update: (id, data) => axios.put(`${API_BASE}/candidates/${id}`, data),
  delete: (id) => axios.delete(`${API_BASE}/candidates/${id}`),
  restore: (id) => axios.post(`${API_BASE}/candidates/${id}/restore`),
  addNote: (id, note) => {
    const formData = new FormData();
    formData.append('note_text', note);
    return axios.post(`${API_BASE}/candidates/${id}/notes`, formData);
  },
  changeStatus: (id, newStatus, notes = null) => 
    axios.put(`${API_BASE}/candidates/${id}/status`, { new_status: newStatus, notes }),
  getStatusHistory: (id) => axios.get(`${API_BASE}/candidates/${id}/status-history`),
  markRestricted: (id, reason, category, notes = null) =>
    axios.post(`${API_BASE}/candidates/${id}/restrict`, { reason, category, notes }),
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
  // Batch upload (procesamiento en background)
  uploadBatch: (files) => {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });
    return axios.post(`${API_BASE}/candidates/upload-batch`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  },
  getBatchStatus: (batchId) => axios.get(`${API_BASE}/candidates/batch/${batchId}`),
  getJobStatus: (jobId) => axios.get(`${API_BASE}/candidates/job/${jobId}`),
  retryJob: (jobId) => axios.post(`${API_BASE}/candidates/job/${jobId}/retry`),
  getQueueStats: () => axios.get(`${API_BASE}/candidates/queue-stats`),
  getDuplicates: (id) => axios.get(`${API_BASE}/candidates/${id}/duplicates`),
  dismissDuplicate: (candidateId, suggestionId) => 
    axios.post(`${API_BASE}/candidates/${candidateId}/dismiss-duplicate/${suggestionId}`),
  merge: (sourceId, targetId, options = {}) =>
    axios.post(`${API_BASE}/candidates/merge`, {
      source_candidate_id: sourceId,
      target_candidate_id: targetId,
      merge_notes: options.mergeNotes ?? true,
      merge_history: options.mergeHistory ?? true
    }),
  downloadCV: (id) => `${API_BASE}/candidates/${id}/download-cv`
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

// Status Config
export const statusAPI = {
  getConfig: () => axios.get(`${API_BASE}/status-config`)
};

// Taxonomy
export const taxonomyAPI = {
  getIndustries: () => axios.get(`${API_BASE}/taxonomy/industries`),
  getFunctionalAreas: () => axios.get(`${API_BASE}/taxonomy/functional-areas`),
  getLookup: () => axios.get(`${API_BASE}/taxonomy/lookup`),
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

// Jobs / Vacantes
export const jobsAPI = {
  getAll: (status = null) => {
    const params = status ? { status } : {};
    return axios.get(`${API_BASE}/jobs`, { params });
  },
  getById: (id) => axios.get(`${API_BASE}/jobs/${id}`),
  create: (data) => axios.post(`${API_BASE}/jobs`, data),
  update: (id, data) => axios.put(`${API_BASE}/jobs/${id}`, data),
  delete: (id) => axios.delete(`${API_BASE}/jobs/${id}`),
  getMatches: (id, threshold = 60, limit = 50) => 
    axios.post(`${API_BASE}/jobs/${id}/match`, null, { params: { threshold, limit } })
};

// Users (Admin)
export const usersAPI = {
  getAll: (includeInactive = false) => 
    axios.get(`${API_BASE}/users`, { params: { include_inactive: includeInactive } }),
  getMe: () => axios.get(`${API_BASE}/users/me`),
  getById: (id) => axios.get(`${API_BASE}/users/${id}`),
  create: (data) => axios.post(`${API_BASE}/users`, data),
  update: (id, data) => axios.put(`${API_BASE}/users/${id}`, data),
  deactivate: (id) => axios.delete(`${API_BASE}/users/${id}`),
  getRecruiters: () => axios.get(`${API_BASE}/users/recruiters`)
};

// Assignments
export const assignmentsAPI = {
  getCandidateAssignments: (candidateId) => 
    axios.get(`${API_BASE}/candidates/${candidateId}/assignments`),
  assignCandidate: (candidateId, recruiterId, notes = null) => 
    axios.post(`${API_BASE}/candidates/${candidateId}/assign`, { 
      candidate_id: candidateId, 
      recruiter_id: recruiterId, 
      notes 
    }),
  unassignCandidate: (candidateId, recruiterId) => 
    axios.delete(`${API_BASE}/candidates/${candidateId}/assign/${recruiterId}`),
  checkCanEdit: (candidateId) => 
    axios.get(`${API_BASE}/candidates/${candidateId}/can-edit`),
  getMyAssignments: () => axios.get(`${API_BASE}/assignments/my`),
  getAllAssignments: () => axios.get(`${API_BASE}/assignments`),
  transferCandidate: (candidateId, fromRecruiterId, toRecruiterId, notes = null) =>
    axios.post(`${API_BASE}/candidates/${candidateId}/transfer`, null, { 
      params: { from_recruiter_id: fromRecruiterId, to_recruiter_id: toRecruiterId, notes }
    })
};

// Exports
export const exportsAPI = {
  exportJobShortlist: (jobId, options = {}) => {
    const params = new URLSearchParams();
    params.append('format', options.format || 'pdf');
    params.append('limit', options.limit || 10);
    params.append('include_risks', options.includeRisks !== false);
    params.append('include_contact_info', options.includeContact || false);
    if (options.clientName) params.append('client_name', options.clientName);
    return axios.post(`${API_BASE}/exports/job/${jobId}?${params.toString()}`);
  },
  exportCandidates: (candidateIds, options = {}) =>
    axios.post(`${API_BASE}/exports/candidates`, {
      source_type: 'custom',
      candidate_ids: candidateIds,
      format: options.format || 'pdf',
      include_risks: options.includeRisks !== false,
      include_contact_info: options.includeContact || false,
      client_name: options.clientName || null
    }),
  getExport: (exportId) => axios.get(`${API_BASE}/exports/${exportId}`),
  listExports: (limit = 50) => axios.get(`${API_BASE}/exports`, { params: { limit } }),
  downloadExport: (exportId) => {
    const token = localStorage.getItem('token');
    return `${API_BASE}/exports/${exportId}/download?token=${token}`;
  }
};

// Smart Folders
export const foldersAPI = {
  getAll: (includeCounts = true) => 
    axios.get(`${API_BASE}/folders`, { params: { include_counts: includeCounts } }),
  getById: (id) => axios.get(`${API_BASE}/folders/${id}`),
  create: (data) => axios.post(`${API_BASE}/folders`, data),
  update: (id, data) => axios.put(`${API_BASE}/folders/${id}`, data),
  delete: (id) => axios.delete(`${API_BASE}/folders/${id}`),
  getCandidates: (id, skip = 0, limit = 50, sortBy = 'match_score') =>
    axios.get(`${API_BASE}/folders/${id}/candidates`, { params: { skip, limit, sort_by: sortBy } }),
  getCount: (id) => axios.get(`${API_BASE}/folders/${id}/count`),
  getAnalytics: (id) => axios.get(`${API_BASE}/folders/${id}/analytics`)
};

export default {
  candidatesAPI,
  atlasAPI,
  searchAPI,
  dashboardAPI,
  statusAPI,
  taxonomyAPI,
  seedAPI,
  jobsAPI,
  usersAPI,
  assignmentsAPI,
  exportsAPI,
  foldersAPI
};