export const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('es-MX', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  }).format(date);
};

export const formatDateTime = (dateString) => {
  if (!dateString) return 'N/A';
  
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('es-MX', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date);
};

export const formatRelativeTime = (dateString) => {
  if (!dateString) return 'N/A';
  
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 1) return 'Hace un momento';
  if (diffMins < 60) return `Hace ${diffMins} min`;
  if (diffHours < 24) return `Hace ${diffHours}h`;
  if (diffDays < 7) return `Hace ${diffDays}d`;
  
  return formatDate(dateString);
};

export const getStatusColor = (status) => {
  const colors = {
    new: 'bg-blue-100 text-blue-800',
    reviewed: 'bg-purple-100 text-purple-800',
    contacted: 'bg-yellow-100 text-yellow-800',
    in_process: 'bg-orange-100 text-orange-800',
    placed: 'bg-green-100 text-green-800',
    archived: 'bg-gray-100 text-gray-800'
  };
  return colors[status] || 'bg-gray-100 text-gray-800';
};

export const getStatusLabel = (status) => {
  const labels = {
    new: 'Nuevo',
    reviewed: 'Revisado',
    contacted: 'Contactado',
    in_process: 'En Proceso',
    placed: 'Colocado',
    archived: 'Archivado'
  };
  return labels[status] || status;
};

export const getSeniorityLabel = (seniority) => {
  const labels = {
    trainee: 'Becario/Trainee',
    entry: 'Entrada',
    junior: 'Junior/Coordinador',
    mid: 'Mid-Level',
    senior: 'Senior',
    lead: 'Lead',
    manager: 'Gerente',
    director: 'Director',
    vp: 'VP',
    c_level: 'C-Level'
  };
  return labels[seniority] || seniority;
};

export const truncateText = (text, maxLength = 100) => {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
};