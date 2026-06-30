import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Checkbox } from '../components/ui/checkbox';
import { Label } from '../components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Alert, AlertDescription } from '../components/ui/alert';
import { 
  AlertCircle, 
  CheckCircle2, 
  Loader2, 
  RefreshCw,
  Edit,
  Check,
  Building2,
  Briefcase,
  TrendingUp,
  Percent,
  ChevronLeft,
  ChevronRight,
  User
} from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';
import { useTaxonomy } from '../contexts/TaxonomyContext';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

const ClassificationReviewPage = () => {
  const { industries, functionalAreas, seniorityLevels } = useTaxonomy();
  
  const [loading, setLoading] = useState(true);
  const [candidates, setCandidates] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [selectedIds, setSelectedIds] = useState([]);
  const [bulkApproving, setBulkApproving] = useState(false);
  
  // Correction dialog state
  const [correctionDialogOpen, setCorrectionDialogOpen] = useState(false);
  const [correctionCandidate, setCorrectionCandidate] = useState(null);
  const [corrections, setCorrections] = useState({
    industry: '',
    functional_area: '',
    seniority: ''
  });
  const [submittingCorrection, setSubmittingCorrection] = useState(false);

  const loadCandidates = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE}/api/atlas/classifications/pending`, {
        params: { page, limit: 20 }
      });
      setCandidates(response.data.candidates || []);
      setTotal(response.data.total || 0);
      setPages(response.data.pages || 1);
    } catch (error) {
      console.error('Error loading pending classifications:', error);
      toast.error('Error cargando clasificaciones pendientes');
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    loadCandidates();
  }, [loadCandidates]);

  const handleApprove = async (candidateId) => {
    try {
      await axios.post(`${API_BASE}/api/atlas/approve-classification/${candidateId}`);
      toast.success('Clasificación aprobada');
      loadCandidates();
    } catch (error) {
      console.error('Error approving:', error);
      toast.error('Error al aprobar', {
        description: error.response?.data?.detail || error.message
      });
    }
  };

  const handleBulkApprove = async () => {
    if (selectedIds.length === 0) {
      toast.error('Selecciona al menos un candidato');
      return;
    }

    setBulkApproving(true);
    try {
      const response = await axios.post(`${API_BASE}/api/atlas/classifications/bulk-approve`, {
        candidate_ids: selectedIds
      });
      toast.success(`${response.data.approved_count} clasificaciones aprobadas`);
      setSelectedIds([]);
      loadCandidates();
    } catch (error) {
      console.error('Error bulk approving:', error);
      toast.error('Error al aprobar', {
        description: error.response?.data?.detail || error.message
      });
    } finally {
      setBulkApproving(false);
    }
  };

  const openCorrectionDialog = (candidate) => {
    setCorrectionCandidate(candidate);
    setCorrections({
      industry: candidate.proposed_classification?.industry || '',
      functional_area: candidate.proposed_classification?.functional_area || '',
      seniority: candidate.proposed_classification?.seniority || ''
    });
    setCorrectionDialogOpen(true);
  };

  const handleCorrect = async () => {
    if (!correctionCandidate) return;

    setSubmittingCorrection(true);
    try {
      await axios.post(
        `${API_BASE}/api/atlas/classifications/correct/${correctionCandidate.id}`,
        corrections
      );
      toast.success('Clasificación corregida y aprobada');
      setCorrectionDialogOpen(false);
      setCorrectionCandidate(null);
      loadCandidates();
    } catch (error) {
      console.error('Error correcting:', error);
      toast.error('Error al corregir', {
        description: error.response?.data?.detail || error.message
      });
    } finally {
      setSubmittingCorrection(false);
    }
  };

  const toggleSelection = (id) => {
    setSelectedIds(prev => 
      prev.includes(id) 
        ? prev.filter(i => i !== id)
        : [...prev, id]
    );
  };

  const selectAll = () => {
    if (selectedIds.length === candidates.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(candidates.map(c => c.id));
    }
  };

  const getConfidenceColor = (score) => {
    if (score >= 0.7) return 'text-amber-600 bg-amber-50';
    if (score >= 0.5) return 'text-orange-600 bg-orange-50';
    return 'text-red-600 bg-red-50';
  };

  const formatConfidence = (score) => {
    return `${Math.round((score || 0) * 100)}%`;
  };

  const getIndustryLabel = (key) => {
    const industry = (industries || []).find(i => i.key === key);
    return industry?.name_es || industry?.label || key || 'Sin industria';
  };

  const getFunctionalAreaLabel = (key) => {
    const area = (functionalAreas || []).find(a => a.key === key);
    return area?.name_es || area?.label || key || 'Sin área';
  };

  const getSeniorityLabel = (key) => {
    const level = (seniorityLevels || []).find(l => l.key === key);
    return level?.label || key || 'Sin nivel';
  };

  if (loading && candidates.length === 0) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-cyan-600" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">Clasificaciones Por Revisar</h1>
            <p className="text-slate-600 mt-1">
              Revisa y aprueba las clasificaciones de IA con baja confianza
            </p>
          </div>
          <div className="flex gap-2">
            <Button 
              variant="outline" 
              onClick={loadCandidates}
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Actualizar
            </Button>
            {selectedIds.length > 0 && (
              <Button 
                onClick={handleBulkApprove}
                disabled={bulkApproving}
                className="bg-green-600 hover:bg-green-700"
              >
                {bulkApproving ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                )}
                Aprobar {selectedIds.length} seleccionados
              </Button>
            )}
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-amber-100 rounded-lg">
                  <AlertCircle className="w-5 h-5 text-amber-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-slate-900">{total}</p>
                  <p className="text-sm text-slate-500">Pendientes de revisión</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-cyan-100 rounded-lg">
                  <Percent className="w-5 h-5 text-cyan-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-slate-900">&lt;75%</p>
                  <p className="text-sm text-slate-500">Umbral de confianza</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-100 rounded-lg">
                  <CheckCircle2 className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-slate-900">{selectedIds.length}</p>
                  <p className="text-sm text-slate-500">Seleccionados</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Candidates List */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Candidatos con Clasificación Pendiente</CardTitle>
                <CardDescription>
                  Confianza de IA menor al 75% - requieren validación humana
                </CardDescription>
              </div>
              {candidates.length > 0 && (
                <Button variant="ghost" size="sm" onClick={selectAll}>
                  {selectedIds.length === candidates.length ? 'Deseleccionar todos' : 'Seleccionar todos'}
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {candidates.length === 0 ? (
              <div className="text-center py-12 text-slate-500">
                <CheckCircle2 className="w-16 h-16 mx-auto mb-4 text-green-400" />
                <p className="text-lg font-medium">¡Todo revisado!</p>
                <p className="text-sm mt-1">No hay clasificaciones pendientes de revisar</p>
              </div>
            ) : (
              <div className="space-y-3">
                {candidates.map((candidate) => (
                  <div
                    key={candidate.id}
                    data-testid={`review-candidate-${candidate.id}`}
                    className={`p-4 border rounded-lg transition-all ${
                      selectedIds.includes(candidate.id)
                        ? 'border-cyan-400 bg-cyan-50/50'
                        : 'border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-start gap-4">
                      {/* Checkbox */}
                      <div className="pt-1">
                        <Checkbox
                          checked={selectedIds.includes(candidate.id)}
                          onCheckedChange={() => toggleSelection(candidate.id)}
                        />
                      </div>

                      {/* Candidate Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 mb-2">
                          <div className="flex items-center gap-2">
                            <User className="w-4 h-4 text-slate-400" />
                            <span className="font-semibold text-slate-900">
                              {candidate.full_name}
                            </span>
                          </div>
                          <Badge className={`${getConfidenceColor(candidate.confidence_score)} text-xs`}>
                            <Percent className="w-3 h-3 mr-1" />
                            {formatConfidence(candidate.confidence_score)} confianza
                          </Badge>
                        </div>

                        <p className="text-sm text-slate-600 mb-3">
                          {candidate.current_title}
                          {candidate.current_company && ` en ${candidate.current_company}`}
                        </p>

                        {/* Proposed Classification */}
                        <div className="bg-slate-50 rounded-lg p-3">
                          <p className="text-xs text-slate-500 mb-2 font-medium">
                            Clasificación propuesta por IA:
                          </p>
                          <div className="grid grid-cols-3 gap-4">
                            <div className="flex items-center gap-2">
                              <Building2 className="w-4 h-4 text-slate-400" />
                              <div>
                                <p className="text-xs text-slate-500">Industria</p>
                                <p className="text-sm font-medium text-slate-700">
                                  {getIndustryLabel(candidate.proposed_classification?.industry)}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <Briefcase className="w-4 h-4 text-slate-400" />
                              <div>
                                <p className="text-xs text-slate-500">Área Funcional</p>
                                <p className="text-sm font-medium text-slate-700">
                                  {getFunctionalAreaLabel(candidate.proposed_classification?.functional_area)}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <TrendingUp className="w-4 h-4 text-slate-400" />
                              <div>
                                <p className="text-xs text-slate-500">Seniority</p>
                                <p className="text-sm font-medium text-slate-700">
                                  {getSeniorityLabel(candidate.proposed_classification?.seniority)}
                                </p>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex flex-col gap-2">
                        <Button
                          size="sm"
                          className="bg-green-600 hover:bg-green-700 text-white"
                          onClick={() => handleApprove(candidate.id)}
                          data-testid={`approve-${candidate.id}`}
                        >
                          <Check className="w-4 h-4 mr-1" />
                          Aprobar
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => openCorrectionDialog(candidate)}
                          data-testid={`correct-${candidate.id}`}
                        >
                          <Edit className="w-4 h-4 mr-1" />
                          Corregir
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Pagination */}
            {pages > 1 && (
              <div className="flex items-center justify-between mt-6 pt-4 border-t">
                <p className="text-sm text-slate-500">
                  Mostrando página {page} de {pages} ({total} total)
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page === 1}
                    onClick={() => setPage(p => p - 1)}
                  >
                    <ChevronLeft className="w-4 h-4 mr-1" />
                    Anterior
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page === pages}
                    onClick={() => setPage(p => p + 1)}
                  >
                    Siguiente
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Correction Dialog */}
        <Dialog open={correctionDialogOpen} onOpenChange={setCorrectionDialogOpen}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Corregir Clasificación</DialogTitle>
              <DialogDescription>
                Ajusta la clasificación de {correctionCandidate?.full_name}
              </DialogDescription>
            </DialogHeader>

            {correctionCandidate && (
              <div className="space-y-4">
                <Alert className="bg-amber-50 border-amber-200">
                  <AlertCircle className="w-4 h-4 text-amber-600" />
                  <AlertDescription className="text-amber-800">
                    Confianza de IA: {formatConfidence(correctionCandidate.confidence_score)}
                  </AlertDescription>
                </Alert>

                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Industria</Label>
                    <Select
                      value={corrections.industry}
                      onValueChange={(value) => setCorrections(prev => ({ ...prev, industry: value }))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Selecciona industria" />
                      </SelectTrigger>
                      <SelectContent>
                        {(industries || []).map(ind => (
                          <SelectItem key={ind.key} value={ind.key}>
                            {ind.name_es || ind.label || ind.key}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>Área Funcional</Label>
                    <Select
                      value={corrections.functional_area}
                      onValueChange={(value) => setCorrections(prev => ({ ...prev, functional_area: value }))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Selecciona área funcional" />
                      </SelectTrigger>
                      <SelectContent>
                        {(functionalAreas || []).map(area => (
                          <SelectItem key={area.key} value={area.key}>
                            {area.name_es || area.label || area.key}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>Seniority</Label>
                    <Select
                      value={corrections.seniority}
                      onValueChange={(value) => setCorrections(prev => ({ ...prev, seniority: value }))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Selecciona nivel" />
                      </SelectTrigger>
                      <SelectContent>
                        {(seniorityLevels || []).map(level => (
                          <SelectItem key={level.key} value={level.key}>
                            {level.label || level.key}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
            )}

            <DialogFooter>
              <Button variant="outline" onClick={() => setCorrectionDialogOpen(false)}>
                Cancelar
              </Button>
              <Button 
                onClick={handleCorrect}
                disabled={submittingCorrection}
                className="bg-cyan-600 hover:bg-cyan-700"
              >
                {submittingCorrection ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Check className="w-4 h-4 mr-2" />
                )}
                Guardar y Aprobar
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};

export default ClassificationReviewPage;
