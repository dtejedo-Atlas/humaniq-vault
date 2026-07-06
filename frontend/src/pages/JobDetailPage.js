import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
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
import { useTaxonomy } from '../contexts/TaxonomyContext';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import JobScorecardConfig from '../components/JobScorecardConfig';
import MatchV3Results, { ACTION_CONFIG } from '../components/MatchV3Results';

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
  const { getIndustryName, getFunctionalAreaName } = useTaxonomy();
  const { user } = useAuth();
  const isTechnical = user?.role === 'admin' || user?.role === 'super_admin';
  
  const [job, setJob] = useState(null);
  const [matches, setMatches] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMatches, setLoadingMatches] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [expandedCards, setExpandedCards] = useState({});
  
  // Export state
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportOptions, setExportOptions] = useState({
    format: 'pdf',
    limit: 10,
    includeRisks: true,
    includeContact: false,
    clientName: ''
  });
  
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';

  useEffect(() => {
    loadJob();
  }, [id]);

  const loadJob = async () => {
    try {
      const response = await jobsAPI.getById(id);
      setJob(response.data);
      // Auto-load matches
      loadMatches();
    } catch (error) {
      console.error('Error loading job:', error);
      toast.error('Error al cargar vacante');
      navigate('/jobs');
    } finally {
      setLoading(false);
    }
  };

  const loadMatches = async () => {
    setLoadingMatches(true);
    try {
      const response = await jobsAPI.getMatches(id, 50, 50);
      setMatches(response.data);
    } catch (error) {
      console.error('Error loading matches:', error);
      toast.error('Error al cargar candidatos');
    } finally {
      setLoadingMatches(false);
    }
  };

  const getSeniorityLabel = (value) => {
    return SENIORITY_OPTIONS.find(o => o.value === value)?.label || value;
  };

  const getMatchColor = (percentage) => {
    if (percentage >= 80) return 'text-green-600 bg-green-100';
    if (percentage >= 60) return 'text-blue-600 bg-blue-100';
    if (percentage >= 50) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  const getProgressColor = (percentage) => {
    if (percentage >= 80) return 'bg-green-500';
    if (percentage >= 60) return 'bg-blue-500';
    if (percentage >= 50) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getRiskSeverityColor = (severity) => {
    const colors = {
      high: 'bg-red-100 text-red-800',
      moderate: 'bg-yellow-100 text-yellow-800',
      low: 'bg-blue-100 text-blue-800',
    };
    return colors[severity] || colors.low;
  };

  const toggleExpanded = (candidateId) => {
    setExpandedCards(prev => ({
      ...prev,
      [candidateId]: !prev[candidateId]
    }));
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const response = await exportsAPI.exportJobShortlist(id, {
        format: exportOptions.format,
        limit: exportOptions.limit,
        includeRisks: exportOptions.includeRisks,
        includeContact: exportOptions.includeContact,
        clientName: exportOptions.clientName || null
      });
      
      // Obtener URL de descarga
      const downloadUrl = `${process.env.REACT_APP_BACKEND_URL}${response.data.download_url}`;
      
      // Crear link temporal para descargar
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = response.data.filename;
      
      // Agregar token al header para autenticación
      const token = localStorage.getItem('atlas_token');
      
      // Usar fetch para descargar con auth
      const fileResponse = await fetch(downloadUrl, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (fileResponse.ok) {
        const blob = await fileResponse.blob();
        const url = window.URL.createObjectURL(blob);
        link.href = url;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        
        toast.success(`Shortlist exportada: ${response.data.candidate_count} candidatos`);
        setShowExportDialog(false);
      } else {
        throw new Error('Error descargando archivo');
      }
    } catch (error) {
      console.error('Export error:', error);
      toast.error(error.response?.data?.detail || 'Error exportando shortlist');
    } finally {
      setExporting(false);
    }
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

        {/* Matching v3 Results (vista técnica) — solo admin/super_admin */}
        {isTechnical && <MatchV3Results jobId={id} />}

        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Users className="w-5 h-5" />
                  Candidatos Compatibles
                </CardTitle>
                {matches && (
                  <CardDescription>
                    {matches.matched_candidates} de {matches.total_candidates} candidatos superan el {matches.threshold_used}% de compatibilidad
                  </CardDescription>
                )}
              </div>
              <div className="flex gap-2">
                {matches?.results?.length > 0 && (
                  <Button 
                    onClick={() => setShowExportDialog(true)} 
                    variant="outline" 
                    size="sm"
                    className="border-indigo-200 text-indigo-700 hover:bg-indigo-50"
                    data-testid="export-shortlist-button"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Exportar Shortlist
                  </Button>
                )}
                <Button onClick={loadMatches} disabled={loadingMatches} variant="outline" size="sm">
                  {loadingMatches && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  Actualizar
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {loadingMatches ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                <span className="ml-2 text-slate-600">Analizando candidatos...</span>
              </div>
            ) : matches?.results?.length === 0 ? (
              <div className="text-center py-8 text-slate-500">
                No se encontraron candidatos que superen el umbral de compatibilidad
              </div>
            ) : (
              <div className="space-y-4">
                {(isTechnical
                  ? matches?.results
                  : [...(matches?.results || [])].sort((a, b) => (b.v3_hms ?? -1) - (a.v3_hms ?? -1))
                )?.map((candidate, index) => (
                  <Card key={candidate.candidate_id} className="border">
                    <Collapsible
                      open={expandedCards[candidate.candidate_id]}
                      onOpenChange={() => toggleExpanded(candidate.candidate_id)}
                    >
                      <div className="p-4">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-4 flex-1">
                            {/* Ranking Number */}
                            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center font-bold text-slate-600">
                              {index + 1}
                            </div>
                            
                            {/* Candidate Info */}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <h4 className="font-semibold text-slate-900 truncate">
                                  {candidate.candidate_name}
                                </h4>
                                {candidate.is_placed && <PlacedBadge />}
                                {isTechnical ? (
                                  <>
                                    <Badge className={getMatchColor(candidate.match_percentage)}>
                                      {candidate.match_percentage}% Match
                                    </Badge>
                                    {candidate.v3_hms != null && (
                                      <Badge
                                        variant="outline"
                                        className={`text-xs ${(ACTION_CONFIG[candidate.v3_action] || {}).color || 'bg-slate-100 text-slate-700'}`}
                                        data-testid="v2-row-v3-badge"
                                        title={`Motor v3 (HMS): ${candidate.v3_hms} — ${(ACTION_CONFIG[candidate.v3_action] || {}).label || candidate.v3_action || ''}`}
                                      >
                                        v3: {candidate.v3_hms} · {(ACTION_CONFIG[candidate.v3_action] || {}).label || candidate.v3_action}
                                      </Badge>
                                    )}
                                  </>
                                ) : candidate.v3_hms != null ? (
                                  <>
                                    <Badge className={getMatchColor(candidate.v3_hms)} data-testid="recruiter-match-badge">
                                      Match {candidate.v3_hms}
                                    </Badge>
                                    {candidate.v3_action && (
                                      <Badge
                                        className={`text-xs border-0 ${(SIMPLE_ACTION[candidate.v3_action] || {}).color || 'bg-slate-100 text-slate-700'}`}
                                        data-testid="recruiter-action-badge"
                                      >
                                        {(SIMPLE_ACTION[candidate.v3_action] || {}).label || candidate.v3_action}
                                      </Badge>
                                    )}
                                  </>
                                ) : (
                                  <Badge className={getMatchColor(candidate.match_percentage)} data-testid="recruiter-match-badge">
                                    {candidate.match_percentage}% Match
                                  </Badge>
                                )}
                              </div>
                              
                              <p className="text-sm text-slate-600 truncate">
                                {candidate.current_title}
                                {candidate.current_company && ` @ ${candidate.current_company}`}
                              </p>
                              
                              <div className="flex flex-wrap gap-2 mt-2">
                                <Badge variant="outline" className="text-xs">
                                  {getFunctionalAreaName(candidate.functional_area)}
                                </Badge>
                                <Badge variant="outline" className="text-xs">
                                  {getIndustryName(candidate.industry)}
                                </Badge>
                                {candidate.years_experience && (
                                  <Badge variant="outline" className="text-xs">
                                    {candidate.years_experience} años exp.
                                  </Badge>
                                )}
                              </div>

                              {/* Quick Indicators */}
                              <div className="flex items-center gap-4 mt-3">
                                {candidate.strengths?.length > 0 && (
                                  <span className="flex items-center text-xs text-green-600">
                                    <CheckCircle2 className="w-3 h-3 mr-1" />
                                    {candidate.strengths.length} fortalezas
                                  </span>
                                )}
                                {candidate.risks?.length > 0 && (
                                  <span className="flex items-center text-xs text-yellow-600">
                                    <AlertTriangle className="w-3 h-3 mr-1" />
                                    {candidate.risks.length} riesgos
                                  </span>
                                )}
                                {isTechnical && candidate.missing_skills?.length > 0 && (
                                  <span className="flex items-center text-xs text-red-600">
                                    <XCircle className="w-3 h-3 mr-1" />
                                    {candidate.missing_skills.length} skills faltantes
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>

                          {/* Expand Button */}
                          <CollapsibleTrigger asChild>
                            <Button variant="ghost" size="sm">
                              {expandedCards[candidate.candidate_id] ? (
                                <ChevronUp className="w-4 h-4" />
                              ) : (
                                <ChevronDown className="w-4 h-4" />
                              )}
                            </Button>
                          </CollapsibleTrigger>
                        </div>
                      </div>

                      <CollapsibleContent>
                        <div className="px-4 pb-4 border-t pt-4 bg-slate-50">
                          {/* Score Breakdown (técnico) — solo admin/super_admin */}
                          {isTechnical && (
                          <div className="mb-4">
                            <h5 className="text-sm font-medium text-slate-700 mb-3">Desglose de Compatibilidad</h5>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                              {Object.entries(candidate.breakdown || {}).map(([key, value]) => {
                                if (typeof value !== 'object' || !value?.score) return null;
                                if (['boosts', 'penalties', 'boost_reasons', 'penalty_reasons', 'weighted_base'].includes(key)) return null;
                                
                                return (
                                  <div key={key} className="bg-white p-2 rounded border">
                                    <div className="flex justify-between items-center mb-1">
                                      <span className="text-xs text-slate-500 capitalize">{key}</span>
                                      <span className="text-xs font-medium">{value.score}%</span>
                                    </div>
                                    <Progress value={value.score} className="h-1.5" />
                                    {value.detail && (
                                      <p className="text-xs text-slate-500 mt-1 truncate" title={value.detail}>
                                        {value.detail}
                                      </p>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                          )}

                          {/* Strengths */}
                          {candidate.strengths?.length > 0 && (
                            <div className="mb-4">
                              <h5 className="text-sm font-medium text-green-700 mb-2 flex items-center gap-1">
                                <CheckCircle2 className="w-4 h-4" />
                                Fortalezas
                              </h5>
                              <ul className="list-disc list-inside text-sm text-slate-600 space-y-1">
                                {candidate.strengths.map((strength, idx) => (
                                  <li key={idx}>{strength}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {/* Risks */}
                          {candidate.risks?.length > 0 && (
                            <div className="mb-4">
                              <h5 className="text-sm font-medium text-yellow-700 mb-2 flex items-center gap-1">
                                <AlertTriangle className="w-4 h-4" />
                                Riesgos Potenciales
                              </h5>
                              <div className="flex flex-wrap gap-2">
                                {candidate.risks.map((risk, idx) => (
                                  <Badge key={idx} className={getRiskSeverityColor(risk.severity)}>
                                    {risk.detail || risk.type}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Missing Skills — solo vista técnica */}
                          {isTechnical && candidate.missing_skills?.length > 0 && (
                            <div>
                              <h5 className="text-sm font-medium text-red-700 mb-2 flex items-center gap-1">
                                <XCircle className="w-4 h-4" />
                                Skills Faltantes
                              </h5>
                              <div className="flex flex-wrap gap-1">
                                {candidate.missing_skills.map((skill, idx) => (
                                  <Badge key={idx} variant="outline" className="text-red-600 border-red-200">
                                    {skill}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* View Profile Button */}
                          <div className="mt-4 pt-3 border-t">
                            <Button 
                              variant="outline" 
                              size="sm"
                              onClick={() => navigate(`/candidates/${candidate.candidate_id}`)}
                            >
                              Ver Perfil Completo
                            </Button>
                          </div>
                        </div>
                      </CollapsibleContent>
                    </Collapsible>
                  </Card>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Export Dialog */}
      <Dialog open={showExportDialog} onOpenChange={setShowExportDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Download className="w-5 h-5 text-indigo-600" />
              Exportar Shortlist
            </DialogTitle>
            <DialogDescription>
              Genera un documento PDF/DOCX con los mejores candidatos para "{job?.title}"
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            {/* Format Selection */}
            <div className="space-y-2">
              <Label>Formato</Label>
              <div className="flex gap-3">
                <Button
                  variant={exportOptions.format === 'pdf' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setExportOptions({...exportOptions, format: 'pdf'})}
                  className={exportOptions.format === 'pdf' ? 'bg-indigo-600' : ''}
                >
                  <FileText className="w-4 h-4 mr-2" />
                  PDF
                </Button>
                <Button
                  variant={exportOptions.format === 'docx' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setExportOptions({...exportOptions, format: 'docx'})}
                  className={exportOptions.format === 'docx' ? 'bg-indigo-600' : ''}
                >
                  <FileSpreadsheet className="w-4 h-4 mr-2" />
                  DOCX
                </Button>
              </div>
            </div>

            {/* Number of candidates */}
            <div className="space-y-2">
              <Label>Número de candidatos</Label>
              <Select
                value={exportOptions.limit.toString()}
                onValueChange={(v) => setExportOptions({...exportOptions, limit: parseInt(v)})}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="5">Top 5 candidatos</SelectItem>
                  <SelectItem value="10">Top 10 candidatos</SelectItem>
                  <SelectItem value="15">Top 15 candidatos</SelectItem>
                  <SelectItem value="20">Top 20 candidatos</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Client Name */}
            <div className="space-y-2">
              <Label>Nombre del cliente (opcional)</Label>
              <Input
                value={exportOptions.clientName}
                onChange={(e) => setExportOptions({...exportOptions, clientName: e.target.value})}
                placeholder="Empresa XYZ"
              />
            </div>

            {/* Options */}
            <div className="space-y-3">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="includeRisks"
                  checked={exportOptions.includeRisks}
                  onCheckedChange={(checked) => setExportOptions({...exportOptions, includeRisks: checked})}
                />
                <Label htmlFor="includeRisks" className="text-sm font-normal">
                  Incluir puntos de atención/riesgos
                </Label>
              </div>
              
              {isAdmin ? (
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="includeContact"
                    checked={exportOptions.includeContact}
                    onCheckedChange={(checked) => setExportOptions({...exportOptions, includeContact: checked})}
                  />
                  <Label htmlFor="includeContact" className="text-sm font-normal">
                    Incluir información de contacto
                  </Label>
                </div>
              ) : (
                <div className="flex items-center space-x-2 opacity-50">
                  <Lock className="w-4 h-4 text-slate-400" />
                  <span className="text-sm text-slate-500">
                    Solo Admin puede incluir datos de contacto
                  </span>
                </div>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowExportDialog(false)}>
              Cancelar
            </Button>
            <Button 
              onClick={handleExport} 
              disabled={exporting}
              className="bg-indigo-600 hover:bg-indigo-700"
            >
              {exporting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Generando...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4 mr-2" />
                  Exportar
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Layout>
  );
};

export default JobDetailPage;
