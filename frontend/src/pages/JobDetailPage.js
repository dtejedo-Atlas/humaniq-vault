import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import Layout from '../components/Layout';
import { saveViewState, loadViewState, restoreScroll } from '../utils/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue 
} from '../components/ui/select';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '../components/ui/collapsible';
import { 
  ArrowLeft, 
  Loader2, 
  Users, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle,
  ChevronDown,
  ChevronUp,
  Briefcase,
  Building,
  Calendar,
  Target,
  Download,
  FileText,
  FileSpreadsheet,
  Lock
} from 'lucide-react';
import { jobsAPI, exportsAPI } from '../api';
import AIMatchReview from '../components/AIMatchReview';
import { useTaxonomy } from '../contexts/TaxonomyContext';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import JobScorecardConfig from '../components/JobScorecardConfig';
import MatchV3Results from '../components/MatchV3Results';

// Etiquetas simples para roles consultora (recruiter/researcher)
const SIMPLE_ACTION = {
  advance_to_screening: { label: 'Entrevistar', color: 'bg-green-100 text-green-800' },
  review_manually: { label: 'Revisar', color: 'bg-yellow-100 text-yellow-800' },
  possible_backup: { label: 'Backup', color: 'bg-blue-100 text-blue-800' },
  low_priority: { label: 'Prioridad baja', color: 'bg-slate-100 text-slate-600' },
  do_not_advance_knockout: { label: 'No avanza', color: 'bg-red-100 text-red-800' },
};
import JobAssignmentsCard from '../components/JobAssignmentsCard';
import { PlacedBadge } from '../components/CandidateBadges';

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

const WORK_SCHEME_LABELS = {
  on_site: 'Presencial',
  hybrid: 'Híbrido',
  remote: 'Remoto',
};

const formatSalaryRange = (job) => {
  const fmt = (v) => `$${Number(v).toLocaleString('es-MX')}`;
  if (job?.salary_min && job?.salary_max) return `${fmt(job.salary_min)} - ${fmt(job.salary_max)} MXN`;
  if (job?.salary_min) return `Desde ${fmt(job.salary_min)} MXN`;
  if (job?.salary_max) return `Hasta ${fmt(job.salary_max)} MXN`;
  return null;
};

const formatLanguageReq = (req) => {
  const [lang, level] = String(req).split(':');
  return level ? `${lang} (${level})` : lang;
};

const JobDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { getIndustryName, getFunctionalAreaName } = useTaxonomy();
  const { user } = useAuth();
  const isTechnical = user?.role === 'admin' || user?.role === 'super_admin';
  
  const savedView = useRef(loadViewState(location.pathname));
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [unifiedCount, setUnifiedCount] = useState(0);

  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';

  useEffect(() => {
    loadJob();
  }, [id]);

  // Persistir scroll para que "Volver" desde una ficha lo restaure
  useEffect(() => {
    const persist = () => saveViewState(location.pathname, { scrollY: window.scrollY });
    window.addEventListener('scroll', persist, { passive: true });
    return () => window.removeEventListener('scroll', persist);
  }, [location.pathname]);

  const loadJob = async () => {
    try {
      const response = await jobsAPI.getById(id);
      setJob(response.data);
    } catch (error) {
      console.error('Error loading job:', error);
      toast.error('Error al cargar vacante');
      navigate('/jobs');
    } finally {
      setLoading(false);
    }
  };

  const handleUnifiedLoaded = (count) => {
    setUnifiedCount(count);
    const y = location.state?.restoreScrollY ?? savedView.current?.scrollY;
    // Dos pasadas: al llegar la lista y cuando el resto de tarjetas (análisis IA, scorecard) ya ocupó su alto
    restoreScroll(y);
    setTimeout(() => restoreScroll(y), 700);
  };

  const getSeniorityLabel = (value) => {
    return SENIORITY_OPTIONS.find(o => o.value === value)?.label || value;
  };


  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/jobs')}>
            <ArrowLeft className="w-4 h-4 mr-1" />
            Volver
          </Button>
        </div>

        {/* Job Info Card */}
        <Card>
          <CardHeader>
            <div className="flex justify-between items-start">
              <div>
                <CardTitle className="text-2xl">{job?.title}</CardTitle>
                {job?.company && (
                  <CardDescription className="text-lg mt-1">{job.company}</CardDescription>
                )}
              </div>
              <Badge className={job?.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}>
                {job?.status === 'active' ? 'Activa' : job?.status}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-slate-500" />
                <span className="text-sm">
                  <span className="text-slate-500">Área:</span>{' '}
                  <span className="font-medium">{getFunctionalAreaName(job?.functional_area)}</span>
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Building className="w-4 h-4 text-slate-500" />
                <span className="text-sm">
                  <span className="text-slate-500">Industria:</span>{' '}
                  <span className="font-medium">{getIndustryName(job?.industry)}</span>
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Briefcase className="w-4 h-4 text-slate-500" />
                <span className="text-sm">
                  <span className="text-slate-500">Nivel:</span>{' '}
                  <span className="font-medium">{getSeniorityLabel(job?.seniority)}</span>
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-slate-500" />
                <span className="text-sm">
                  <span className="text-slate-500">Experiencia:</span>{' '}
                  <span className="font-medium">
                    {job?.min_experience}{job?.max_experience ? `-${job.max_experience}` : '+'} años
                  </span>
                </span>
              </div>
            </div>

            {(job?.required_skills?.length > 0 || job?.preferred_skills?.length > 0) && (
              <div className="border-t pt-4">
                {job?.required_skills?.length > 0 && (
                  <div className="mb-2">
                    <span className="text-sm text-slate-500 mr-2">Skills requeridos:</span>
                    {job.required_skills.map((skill, idx) => (
                      <Badge key={idx} variant="secondary" className="mr-1 mb-1">{skill}</Badge>
                    ))}
                  </div>
                )}
                {job?.preferred_skills?.length > 0 && (
                  <div>
                    <span className="text-sm text-slate-500 mr-2">Skills deseables:</span>
                    {job.preferred_skills.map((skill, idx) => (
                      <Badge key={idx} variant="outline" className="mr-1 mb-1">{skill}</Badge>
                    ))}
                  </div>
                )}
              </div>
            )}
            {(job?.job_objective || job?.role_context || job?.responsibilities || job?.required_experience || job?.non_negotiables || job?.salary_min || job?.salary_max || job?.work_scheme || job?.schedule || job?.language_requirements?.length > 0) && (
              <div className="border-t pt-4 mt-4" data-testid="job-details-section">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Detalles de la Vacante</h3>
                <div className="space-y-3">
                  {job?.job_objective && (
                    <div data-testid="job-detail-objective">
                      <span className="text-sm text-slate-500 block">Objetivo del puesto</span>
                      <p className="text-sm whitespace-pre-line">{job.job_objective}</p>
                    </div>
                  )}
                  {job?.role_context && (
                    <div data-testid="job-detail-role-context">
                      <span className="text-sm text-slate-500 block">Contexto del rol</span>
                      <p className="text-sm whitespace-pre-line">{job.role_context}</p>
                    </div>
                  )}
                  {job?.responsibilities && (
                    <div data-testid="job-detail-responsibilities">
                      <span className="text-sm text-slate-500 block">Responsabilidades</span>
                      <p className="text-sm whitespace-pre-line">{job.responsibilities}</p>
                    </div>
                  )}
                  {job?.required_experience && (
                    <div data-testid="job-detail-required-experience">
                      <span className="text-sm text-slate-500 block">Experiencia requerida</span>
                      <p className="text-sm whitespace-pre-line">{job.required_experience}</p>
                    </div>
                  )}
                  {job?.non_negotiables && (
                    <div data-testid="job-detail-non-negotiables">
                      <span className="text-sm text-slate-500 block">Requisitos no negociables</span>
                      <p className="text-sm whitespace-pre-line">{job.non_negotiables}</p>
                    </div>
                  )}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {formatSalaryRange(job) && (
                      <div data-testid="job-detail-salary">
                        <span className="text-sm text-slate-500 block">Rango salarial</span>
                        <p className="text-sm font-medium">{formatSalaryRange(job)}</p>
                      </div>
                    )}
                    {job?.work_scheme && (
                      <div data-testid="job-detail-work-scheme">
                        <span className="text-sm text-slate-500 block">Esquema</span>
                        <p className="text-sm font-medium">{WORK_SCHEME_LABELS[job.work_scheme] || job.work_scheme}</p>
                      </div>
                    )}
                    {job?.schedule && (
                      <div data-testid="job-detail-schedule">
                        <span className="text-sm text-slate-500 block">Jornada</span>
                        <p className="text-sm font-medium">{job.schedule}</p>
                      </div>
                    )}
                    {job?.language_requirements?.length > 0 && (
                      <div data-testid="job-detail-languages">
                        <span className="text-sm text-slate-500 block">Idiomas</span>
                        <div>
                          {job.language_requirements.map((req) => (
                            <Badge key={req} variant="secondary" className="mr-1 mb-1">{formatLanguageReq(req)}</Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Candidatos Asignados (pipeline de la vacante) */}
        <JobAssignmentsCard jobId={id} />

        {/* Scorecard v3 Config — visible para todos los roles */}
        <JobScorecardConfig jobId={id} />

        {/* Flujo unificado: v3 (capa 1) + Afinar con IA (capa 2) — una sola lista */}
        <MatchV3Results jobId={id} jobTitle={job?.title} technical={isTechnical} onResultsChange={handleUnifiedLoaded} />

        <AIMatchReview jobId={id} hasMatches={unifiedCount > 0} />

      </div>

      {/* Export Dialog */}
    </Layout>
  );
};

export default JobDetailPage;
