import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
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
import { Plus, Briefcase, Loader2, Trash2, Eye, MapPin, Building2, Home, Building } from 'lucide-react';
import { jobsAPI } from '../api';
import { useTaxonomy } from '../contexts/TaxonomyContext';
import { toast } from 'sonner';
import { getSeniorityLabel, getWorkSchemeLabel, getStateLabel } from '../constants/mexicoStates';

const JobsPage = () => {
  const navigate = useNavigate();
  const { getIndustryName, getFunctionalAreaName } = useTaxonomy();
  
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadJobs();
  }, []);

  const loadJobs = async () => {
    try {
      const response = await jobsAPI.getAll();
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
      await jobsAPI.create(jobData);
      toast.success('Vacante creada correctamente');
      setCreateDialogOpen(false);
      loadJobs();
    } catch (error) {
      console.error('Error creating job:', error);
      toast.error('Error al crear vacante');
    } finally {
      setCreating(false);
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
    };
    const labels = {
      active: 'Activa',
      paused: 'Pausada',
      closed: 'Cerrada',
      draft: 'Borrador',
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
          
          <Button data-testid="create-job-button" onClick={() => setCreateDialogOpen(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Nueva Vacante
          </Button>
        </div>

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
                      <Button 
                        variant="ghost" 
                        size="sm"
                        onClick={(e) => handleDeleteJob(job.id, e)}
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
