import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import JobFormWizard from '../components/JobFormWizard';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import { Plus, Briefcase, Loader2, Trash2, Eye, MapPin, Building2, Home, Building, Archive, RotateCcw } from 'lucide-react';
import { jobsAPI } from '../api';
import { useTaxonomy } from '../contexts/TaxonomyContext';
import { toast } from 'sonner';
import { getSeniorityLabel, getWorkSchemeLabel, getStateLabel } from '../constants/mexicoStates';

const JobsPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const canDelete = ['admin', 'super_admin'].includes(user?.role);
  const { getIndustryName, getFunctionalAreaName } = useTaxonomy();
  
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [similar, setSimilar] = useState({ open: false, jobId: null, jobs: [], selected: [] });

  useEffect(() => {
    loadJobs();
  }, [showArchived]);

  const loadJobs = async () => {
    setLoading(true);
    try {
      const response = await jobsAPI.getAll(showArchived ? 'archived' : null);
      setJobs(response.data);
    } catch (error) {
      console.error('Error loading jobs:', error);
      toast.error('Error al cargar vacantes');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateJob = async (jobData) => {
    setCreating(true);
    try {
      const res = await jobsAPI.create(jobData);
      toast.success('Vacante creada correctamente');
      setCreateDialogOpen(false);
      loadJobs();
      const similarRes = await jobsAPI.getSimilarArchived({
        title: jobData.title,
        presentation_area: jobData.presentation_area,
        presentation_subarea: jobData.presentation_subarea,
        functional_area: jobData.functional_area,
        exclude_job_id: res.data.id,
      });
      if (similarRes.data.total > 0) {
        setSimilar({ open: true, jobId: res.data.id, jobs: similarRes.data.jobs, selected: [] });
      }
    } catch (error) {
      console.error('Error creating job:', error);
      toast.error('Error al crear vacante');
    } finally {
      setCreating(false);
    }
  };

  const toggleReuse = (candidateId, sourceJobId) => {
    setSimilar((prev) => {
      const exists = prev.selected.find((s) => s.candidateId === candidateId);
      return {
        ...prev,
        selected: exists
          ? prev.selected.filter((s) => s.candidateId !== candidateId)
          : [...prev.selected, { candidateId, sourceJobId }],
      };
    });
  };

  const handleReuseCandidates = async () => {
    const bySource = similar.selected.reduce((acc, s) => {
      acc[s.sourceJobId] = [...(acc[s.sourceJobId] || []), s.candidateId];
      return acc;
    }, {});
    try {
      let total = 0;
      for (const [sourceJobId, ids] of Object.entries(bySource)) {
        const res = await jobsAPI.reuseCandidates(similar.jobId, sourceJobId, ids);
        total += res.data.assigned.length;
      }
      toast.success(`${total} candidatos reutilizados en la nueva vacante`);
      setSimilar({ open: false, jobId: null, jobs: [], selected: [] });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al reutilizar candidatos');
    }
  };

  const handleArchive = async (job, e) => {
    e.stopPropagation();
    if (!window.confirm(`¿Archivar "${job.title}"? Conserva candidatos, etapas y notas.`)) return;
    try {
      await jobsAPI.archive(job.id);
      toast.success('Vacante archivada');
      loadJobs();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al archivar');
    }
  };

  const handleReactivate = async (job, e) => {
    e.stopPropagation();
    try {
      await jobsAPI.reactivate(job.id);
      toast.success('Vacante reactivada');
      loadJobs();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al reactivar');
    }
  };

  const handleDeleteJob = async (jobId, e) => {
    e.stopPropagation();
    if (!window.confirm('¿Estás seguro de eliminar esta vacante?')) return;

    try {
      await jobsAPI.delete(jobId);
      toast.success('Vacante eliminada');
      loadJobs();
    } catch (error) {
      toast.error('Error al eliminar vacante');
    }
  };

  const getStatusBadge = (status) => {
    const colors = {
      active: 'bg-green-100 text-green-800',
      paused: 'bg-yellow-100 text-yellow-800',
      closed: 'bg-gray-100 text-gray-800',
      draft: 'bg-blue-100 text-blue-800',
      archived: 'bg-slate-200 text-slate-700',
    };
    const labels = {
      active: 'Activa',
      paused: 'Pausada',
      closed: 'Cerrada',
      draft: 'Borrador',
      archived: 'Archivada',
    };
    return <Badge className={colors[status] || colors.draft}>{labels[status] || status}</Badge>;
  };

  const getWorkSchemeIcon = (scheme) => {
    switch (scheme) {
      case 'remote': return <Home className="w-3.5 h-3.5" />;
      case 'hybrid': return <Building className="w-3.5 h-3.5" />;
      default: return <Building2 className="w-3.5 h-3.5" />;
    }
  };

  const formatLocation = (job) => {
    const parts = [];
    if (job.location_city) parts.push(job.location_city);
    if (job.location_state) {
      const stateLabel = job.location_country === 'México' 
        ? getStateLabel(job.location_state) 
        : job.location_state;
      parts.push(stateLabel);
    }
    return parts.length > 0 ? parts.join(', ') : null;
  };

  const formatSalary = (job) => {
    if (!job.salary_min && !job.salary_max) return null;
    const formatter = new Intl.NumberFormat('es-MX', { 
      style: 'currency', 
      currency: 'MXN', 
      maximumFractionDigits: 0 
    });
    if (job.salary_min && job.salary_max) {
      return `${formatter.format(job.salary_min)} - ${formatter.format(job.salary_max)}`;
    }
    if (job.salary_min) return `Desde ${formatter.format(job.salary_min)}`;
    return `Hasta ${formatter.format(job.salary_max)}`;
  };

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">Vacantes</h1>
            <p className="text-slate-600 mt-1">Gestiona vacantes y encuentra candidatos compatibles</p>
          </div>
          
          <div className="flex items-center gap-2">
            <Button
              variant={showArchived ? 'default' : 'outline'}
              onClick={() => setShowArchived((v) => !v)}
              data-testid="toggle-archived-jobs"
            >
              <Archive className="w-4 h-4 mr-2" />
              {showArchived ? 'Ver activas' : 'Ver archivadas'}
            </Button>
            <Button data-testid="create-job-button" onClick={() => setCreateDialogOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Nueva Vacante
            </Button>
          </div>
        </div>

        {/* Reutilizar candidatos de vacantes archivadas similares */}
        <Dialog open={similar.open} onOpenChange={(open) => setSimilar((prev) => ({ ...prev, open }))}>
          <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="similar-archived-dialog">
            <DialogHeader>
              <DialogTitle>Vacantes archivadas similares</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-slate-600">
              Encontramos vacantes archivadas parecidas. Selecciona candidatos para reutilizarlos en la nueva vacante.
            </p>
            <div className="space-y-4">
              {similar.jobs.map((job) => (
                <div key={job.id} className="border border-slate-200 rounded-lg p-3" data-testid={`similar-job-${job.id}`}>
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium text-slate-900 truncate">{job.title}</p>
                      <p className="text-xs text-slate-500">{job.company || 'Sin empresa'} · {job.match_reasons.join(' · ')}</p>
                    </div>
                    <Badge variant="outline">{job.candidates.length} candidatos</Badge>
                  </div>
                  <div className="mt-2 space-y-1">
                    {job.candidates.length === 0 && <p className="text-xs text-slate-400">Sin candidatos asignados</p>}
                    {job.candidates.map((cand) => (
                      <label
                        key={cand.id}
                        className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer"
                        data-testid={`reuse-candidate-${cand.id}`}
                      >
                        <input
                          type="checkbox"
                          checked={!!similar.selected.find((s) => s.candidateId === cand.id)}
                          onChange={() => toggleReuse(cand.id, job.id)}
                        />
                        <span className="truncate">
                          {cand.full_name}
                          {cand.current_title ? ` — ${cand.current_title}` : ''}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setSimilar({ open: false, jobId: null, jobs: [], selected: [] })}>
                Omitir
              </Button>
              <Button
                disabled={similar.selected.length === 0}
                onClick={handleReuseCandidates}
                data-testid="reuse-candidates-confirm"
              >
                Reutilizar {similar.selected.length} candidatos
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Create Job Dialog with Wizard */}
        <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Crear Nueva Vacante</DialogTitle>
            </DialogHeader>
            <JobFormWizard
              onSubmit={handleCreateJob}
              onCancel={() => setCreateDialogOpen(false)}
              loading={creating}
            />
          </DialogContent>
        </Dialog>

        {/* Jobs List */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-cyan-600" />
          </div>
        ) : jobs.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Briefcase className="w-12 h-12 text-slate-300 mb-4" />
              <h3 className="text-lg font-medium text-slate-900 mb-2">No hay vacantes</h3>
              <p className="text-slate-500 mb-4">Crea tu primera vacante para comenzar a hacer matching</p>
              <Button onClick={() => setCreateDialogOpen(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Crear Vacante
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4">
            {jobs.map(job => (
              <Card 
                key={job.id} 
                className="cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => navigate(`/jobs/${job.id}`)}
                data-testid={`job-card-${job.id}`}
              >
                <CardContent className="p-6">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-lg font-semibold text-slate-900">{job.title}</h3>
                        {getStatusBadge(job.status)}
                        {job.work_scheme && (
                          <Badge variant="outline" className="text-cyan-700 border-cyan-200 bg-cyan-50 flex items-center gap-1">
                            {getWorkSchemeIcon(job.work_scheme)}
                            {getWorkSchemeLabel(job.work_scheme)}
                          </Badge>
                        )}
                      </div>
                      
                      <div className="flex items-center gap-4 text-sm text-slate-600 mb-3">
                        {job.company && <span>{job.company}</span>}
                        {formatLocation(job) && (
                          <span className="flex items-center gap-1">
                            <MapPin className="w-3.5 h-3.5" />
                            {formatLocation(job)}
                          </span>
                        )}
                        {formatSalary(job) && (
                          <span className="text-green-700 font-medium">{formatSalary(job)}</span>
                        )}
                      </div>
                      
                      <div className="flex flex-wrap gap-2 mb-3">
                        <Badge variant="outline">
                          {getFunctionalAreaName(job.functional_area)}
                        </Badge>
                        <Badge variant="outline">
                          {getIndustryName(job.industry)}
                        </Badge>
                        <Badge variant="outline">
                          {getSeniorityLabel(job.seniority)}
                        </Badge>
                        <Badge variant="outline">
                          {job.min_experience}
                          {job.max_experience ? `-${job.max_experience}` : '+'} años exp.
                        </Badge>
                      </div>

                      {job.job_objective && (
                        <p className="text-sm text-slate-500 line-clamp-2">{job.job_objective}</p>
                      )}
                    </div>

                    <div className="flex items-center gap-2 ml-4">
                      <Button 
                        variant="ghost" 
                        size="sm"
                        onClick={(e) => { e.stopPropagation(); navigate(`/jobs/${job.id}`); }}
                      >
                        <Eye className="w-4 h-4 mr-1" />
                        Ver Matches
                      </Button>
                      {job.status === 'archived' ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => handleReactivate(job, e)}
                          data-testid={`reactivate-job-${job.id}`}
                          className="text-cyan-700 hover:bg-cyan-50"
                        >
                          <RotateCcw className="w-4 h-4 mr-1" />
                          Reactivar
                        </Button>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => handleArchive(job, e)}
                          data-testid={`archive-job-${job.id}`}
                          className="text-slate-600 hover:bg-slate-100"
                        >
                          <Archive className="w-4 h-4 mr-1" />
                          Archivar
                        </Button>
                      )}
                      <Button 
                        variant="ghost" 
                        size="sm"
                        onClick={(e) => handleDeleteJob(job.id, e)}
                        disabled={!canDelete}
                        title={!canDelete ? 'Solo administradores pueden eliminar vacantes' : 'Eliminar vacante'}
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default JobsPage;
