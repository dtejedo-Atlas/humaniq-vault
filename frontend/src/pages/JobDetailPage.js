import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
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
  Target
} from 'lucide-react';
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

const JobDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { getIndustryName, getFunctionalAreaName } = useTaxonomy();
  
  const [job, setJob] = useState(null);
  const [matches, setMatches] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMatches, setLoadingMatches] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [expandedCards, setExpandedCards] = useState({});

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
          </CardContent>
        </Card>

        {/* Matches Section */}
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
              <Button onClick={loadMatches} disabled={loadingMatches} variant="outline" size="sm">
                {loadingMatches && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                Actualizar
              </Button>
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
                {matches?.results?.map((candidate, index) => (
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
                                <Badge className={getMatchColor(candidate.match_percentage)}>
                                  {candidate.match_percentage}% Match
                                </Badge>
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
                                {candidate.missing_skills?.length > 0 && (
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
                          {/* Score Breakdown */}
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

                          {/* Missing Skills */}
                          {candidate.missing_skills?.length > 0 && (
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
    </Layout>
  );
};

export default JobDetailPage;
