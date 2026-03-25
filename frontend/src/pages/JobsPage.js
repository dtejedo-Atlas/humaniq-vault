import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from '../components/ui/dialog';
import { Plus, Briefcase, Users, Loader2, Trash2, Eye } from 'lucide-react';
import { jobsAPI } from '../api';
import { useTaxonomy } from '../contexts/TaxonomyContext';
import { toast } from 'sonner';

const SENIORITY_OPTIONS = [
  { value: 'intern', label: 'Becario / Intern' },
  { value: 'junior', label: 'Junior / Analista' },
  { value: 'mid', label: 'Coordinador / Especialista' },
  { value: 'senior', label: 'Senior / Lead' },
  { value: 'manager', label: 'Gerente / Manager' },
  { value: 'senior_manager', label: 'Senior Manager' },
  { value: 'director', label: 'Director' },
  { value: 'vp', label: 'VP / Vicepresidente' },
  { value: 'c_level', label: 'C-Level (CFO, COO, etc.)' },
  { value: 'ceo', label: 'CEO / Director General' },
];

const JobsPage = () => {
  const navigate = useNavigate();
  const { getIndustryOptions, getFunctionalAreaOptions, getIndustryName, getFunctionalAreaName } = useTaxonomy();
  
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState({
    title: '',
    company: '',
    industry: '',
    functional_area: '',
    seniority: 'manager',
    min_experience: 5,
    max_experience: '',
    required_skills: '',
    preferred_skills: '',
    responsibilities: '',
    requirements: '',
    description: '',
  });

  const industries = getIndustryOptions();
  const functionalAreas = getFunctionalAreaOptions();

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

  const handleCreateJob = async () => {
    if (!formData.title || !formData.industry || !formData.functional_area) {
      toast.error('Por favor completa los campos requeridos');
      return;
    }

    setCreating(true);
    try {
      const jobData = {
        ...formData,
        min_experience: parseInt(formData.min_experience) || 0,
        max_experience: formData.max_experience ? parseInt(formData.max_experience) : null,
        required_skills: formData.required_skills.split(',').map(s => s.trim()).filter(Boolean),
        preferred_skills: formData.preferred_skills.split(',').map(s => s.trim()).filter(Boolean),
      };

      await jobsAPI.create(jobData);
      toast.success('Vacante creada correctamente');
      setCreateDialogOpen(false);
      resetForm();
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

  const resetForm = () => {
    setFormData({
      title: '',
      company: '',
      industry: '',
      functional_area: '',
      seniority: 'manager',
      min_experience: 5,
      max_experience: '',
      required_skills: '',
      preferred_skills: '',
      responsibilities: '',
      requirements: '',
      description: '',
    });
  };

  const getSeniorityLabel = (value) => {
    return SENIORITY_OPTIONS.find(o => o.value === value)?.label || value;
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

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">Vacantes</h1>
            <p className="text-slate-600 mt-1">Gestiona vacantes y encuentra candidatos compatibles</p>
          </div>
          
          <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button data-testid="create-job-button">
                <Plus className="w-4 h-4 mr-2" />
                Nueva Vacante
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Crear Nueva Vacante</DialogTitle>
                <DialogDescription>
                  Define los requisitos del puesto para encontrar candidatos compatibles
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4 py-4">
                {/* Título y Empresa */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="title">Título del Puesto *</Label>
                    <Input
                      id="title"
                      placeholder="Ej: Gerente de Operaciones"
                      value={formData.title}
                      onChange={(e) => setFormData({...formData, title: e.target.value})}
                      data-testid="job-title-input"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="company">Empresa (opcional)</Label>
                    <Input
                      id="company"
                      placeholder="Nombre de la empresa"
                      value={formData.company}
                      onChange={(e) => setFormData({...formData, company: e.target.value})}
                    />
                  </div>
                </div>

                {/* Área e Industria */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Área Funcional *</Label>
                    <Select
                      value={formData.functional_area}
                      onValueChange={(v) => setFormData({...formData, functional_area: v})}
                    >
                      <SelectTrigger data-testid="job-area-select">
                        <SelectValue placeholder="Seleccionar área" />
                      </SelectTrigger>
                      <SelectContent>
                        {functionalAreas.map(area => (
                          <SelectItem key={area.value} value={area.value}>
                            {area.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Industria *</Label>
                    <Select
                      value={formData.industry}
                      onValueChange={(v) => setFormData({...formData, industry: v})}
                    >
                      <SelectTrigger data-testid="job-industry-select">
                        <SelectValue placeholder="Seleccionar industria" />
                      </SelectTrigger>
                      <SelectContent>
                        {industries.map(ind => (
                          <SelectItem key={ind.value} value={ind.value}>
                            {ind.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* Seniority y Experiencia */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label>Nivel de Seniority</Label>
                    <Select
                      value={formData.seniority}
                      onValueChange={(v) => setFormData({...formData, seniority: v})}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {SENIORITY_OPTIONS.map(opt => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="min_exp">Exp. Mínima (años)</Label>
                    <Input
                      id="min_exp"
                      type="number"
                      min="0"
                      value={formData.min_experience}
                      onChange={(e) => setFormData({...formData, min_experience: e.target.value})}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="max_exp">Exp. Máxima (años)</Label>
                    <Input
                      id="max_exp"
                      type="number"
                      min="0"
                      placeholder="Opcional"
                      value={formData.max_experience}
                      onChange={(e) => setFormData({...formData, max_experience: e.target.value})}
                    />
                  </div>
                </div>

                {/* Skills */}
                <div className="space-y-2">
                  <Label htmlFor="required_skills">Skills Requeridos</Label>
                  <Input
                    id="required_skills"
                    placeholder="Separados por coma: Lean Manufacturing, SAP, Six Sigma"
                    value={formData.required_skills}
                    onChange={(e) => setFormData({...formData, required_skills: e.target.value})}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="preferred_skills">Skills Deseables</Label>
                  <Input
                    id="preferred_skills"
                    placeholder="Separados por coma: KPIs, ERP, Inglés"
                    value={formData.preferred_skills}
                    onChange={(e) => setFormData({...formData, preferred_skills: e.target.value})}
                  />
                </div>

                {/* Descripción */}
                <div className="space-y-2">
                  <Label htmlFor="description">Descripción del Puesto</Label>
                  <Textarea
                    id="description"
                    placeholder="Describe el puesto, responsabilidades principales y contexto del rol..."
                    rows={4}
                    value={formData.description}
                    onChange={(e) => setFormData({...formData, description: e.target.value})}
                  />
                </div>
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
                  Cancelar
                </Button>
                <Button onClick={handleCreateJob} disabled={creating} data-testid="save-job-button">
                  {creating && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  Crear Vacante
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        {/* Jobs List */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
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
                      </div>
                      
                      {job.company && (
                        <p className="text-slate-600 mb-2">{job.company}</p>
                      )}
                      
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

                      {job.required_skills?.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {job.required_skills.slice(0, 5).map((skill, idx) => (
                            <Badge key={idx} variant="secondary" className="text-xs">
                              {skill}
                            </Badge>
                          ))}
                          {job.required_skills.length > 5 && (
                            <Badge variant="secondary" className="text-xs">
                              +{job.required_skills.length - 5} más
                            </Badge>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
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
