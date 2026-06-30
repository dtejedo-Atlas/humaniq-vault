import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../components/ui/dialog';
import { Checkbox } from '../components/ui/checkbox';
import { Label } from '../components/ui/label';
import { Alert, AlertDescription } from '../components/ui/alert';
import { 
  Users, 
  AlertTriangle, 
  Merge, 
  Eye, 
  Loader2,
  CheckCircle2,
  Calendar,
  Briefcase,
  Mail,
  ArrowRight,
  RefreshCw,
  Trash2,
  AlertCircle,
  Info
} from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

const DuplicatesPage = () => {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [duplicateGroups, setDuplicateGroups] = useState([]);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [merging, setMerging] = useState(false);
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false);
  const [mergeOptions, setMergeOptions] = useState({
    merge_experience: true,
    merge_education: true,
    merge_skills: true,
    merge_notes: true,
    keep_all_cvs: true,
    use_secondary_contact: false
  });
  const [primaryCandidateId, setPrimaryCandidateId] = useState(null);
  
  // Orphan records state
  const [orphanDialogOpen, setOrphanDialogOpen] = useState(false);
  const [orphanRecords, setOrphanRecords] = useState(null);
  const [loadingOrphans, setLoadingOrphans] = useState(false);
  const [cleaningOrphans, setCleaningOrphans] = useState(false);
  const [selectedOrphans, setSelectedOrphans] = useState([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsRes, groupsRes] = await Promise.all([
        axios.get(`${API_BASE}/api/duplicates/stats`),
        axios.get(`${API_BASE}/api/duplicates/review`)
      ]);
      setStats(statsRes.data);
      setDuplicateGroups(groupsRes.data.duplicate_groups || []);
    } catch (error) {
      console.error('Error loading duplicates:', error);
      toast.error('Error cargando datos de duplicados');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectGroup = (group) => {
    setSelectedGroup(group);
    // Auto-select the first candidate as primary (can be changed)
    if (group.candidates.length > 0) {
      setPrimaryCandidateId(group.candidates[0].id);
    }
  };

  const handleMerge = async () => {
    if (!selectedGroup || !primaryCandidateId) {
      toast.error('Debes seleccionar un candidato principal');
      return;
    }
    
    const candidates = selectedGroup.candidates;
    const secondaryIds = candidates
      .filter(c => c.id !== primaryCandidateId)
      .map(c => c.id);

    if (secondaryIds.length === 0) {
      toast.error('No hay candidatos secundarios para fusionar');
      return;
    }

    setMerging(true);
    try {
      // Use merge-multiple endpoint for any number of candidates
      const response = await axios.post(`${API_BASE}/api/candidates/merge-multiple`, {
        primary_candidate_id: primaryCandidateId,
        secondary_candidate_ids: secondaryIds,
        ...mergeOptions
      });
      
      toast.success(
        `${response.data.total_merged} candidatos fusionados exitosamente`,
        { description: `ID principal: ${primaryCandidateId.slice(0, 8)}...` }
      );
      setMergeDialogOpen(false);
      setSelectedGroup(null);
      setPrimaryCandidateId(null);
      loadData();
    } catch (error) {
      console.error('Error merging:', error);
      const errorMessage = error.response?.data?.detail || 
                          error.response?.data?.message || 
                          error.message || 
                          'Error desconocido al fusionar candidatos';
      toast.error('Error al fusionar', { description: errorMessage });
    } finally {
      setMerging(false);
    }
  };

  const loadOrphanRecords = async () => {
    setLoadingOrphans(true);
    try {
      const res = await axios.get(`${API_BASE}/api/duplicates/orphan-records`);
      setOrphanRecords(res.data);
      setSelectedOrphans([]);
    } catch (error) {
      console.error('Error loading orphans:', error);
      toast.error('Error cargando registros huérfanos', {
        description: error.response?.data?.detail || error.message
      });
    } finally {
      setLoadingOrphans(false);
    }
  };

  const handleOpenOrphanDialog = async () => {
    setOrphanDialogOpen(true);
    await loadOrphanRecords();
  };

  const handleCleanupOrphans = async () => {
    if (selectedOrphans.length === 0) {
      toast.error('Selecciona al menos un registro para eliminar');
      return;
    }

    setCleaningOrphans(true);
    try {
      const res = await axios.post(`${API_BASE}/api/duplicates/cleanup-orphans`, selectedOrphans);
      toast.success(`${res.data.deleted_count} registros eliminados`);
      await loadOrphanRecords();
      loadData(); // Refresh main stats
    } catch (error) {
      console.error('Error cleaning orphans:', error);
      toast.error('Error eliminando registros', {
        description: error.response?.data?.detail || error.message
      });
    } finally {
      setCleaningOrphans(false);
    }
  };

  const toggleOrphanSelection = (id) => {
    setSelectedOrphans(prev => 
      prev.includes(id) 
        ? prev.filter(i => i !== id)
        : [...prev, id]
    );
  };

  const selectAllOrphans = () => {
    if (orphanRecords?.orphans) {
      setSelectedOrphans(orphanRecords.orphans.map(o => o.id));
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('es-MX', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  // Get primary candidate data from selected group
  const getPrimaryCandidate = () => {
    if (!selectedGroup || !primaryCandidateId) return null;
    return selectedGroup.candidates.find(c => c.id === primaryCandidateId);
  };

  // Get secondary candidates
  const getSecondaryCandidates = () => {
    if (!selectedGroup || !primaryCandidateId) return [];
    return selectedGroup.candidates.filter(c => c.id !== primaryCandidateId);
  };

  if (loading) {
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
            <h1 className="text-3xl font-bold text-slate-900">Gestión de Duplicados</h1>
            <p className="text-slate-600 mt-1">Revisa y fusiona candidatos duplicados</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={handleOpenOrphanDialog}>
              <Trash2 className="w-4 h-4 mr-2" />
              Limpiar Huérfanos
            </Button>
            <Button variant="outline" onClick={loadData}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Actualizar
            </Button>
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-amber-100 rounded-lg">
                    <AlertTriangle className="w-5 h-5 text-amber-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-slate-900">{stats.total_duplicate_groups}</p>
                    <p className="text-sm text-slate-500">Grupos duplicados</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-red-100 rounded-lg">
                    <Users className="w-5 h-5 text-red-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-slate-900">{stats.total_duplicate_records}</p>
                    <p className="text-sm text-slate-500">Registros afectados</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-100 rounded-lg">
                    <Mail className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-slate-900">{stats.by_match_type?.email || 0}</p>
                    <p className="text-sm text-slate-500">Por email</p>
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
                    <p className="text-2xl font-bold text-slate-900">{stats.total_merges_performed}</p>
                    <p className="text-sm text-slate-500">Merges realizados</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Duplicate Groups */}
        <div className="grid grid-cols-2 gap-6">
          {/* List */}
          <Card>
            <CardHeader>
              <CardTitle>Grupos de Duplicados</CardTitle>
              <CardDescription>
                Selecciona un grupo para ver el detalle y fusionar
              </CardDescription>
            </CardHeader>
            <CardContent>
              {duplicateGroups.length === 0 ? (
                <div className="text-center py-8 text-slate-500">
                  <CheckCircle2 className="w-12 h-12 mx-auto mb-3 text-green-500" />
                  <p>No hay duplicados detectados</p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[500px] overflow-y-auto">
                  {duplicateGroups.map((group) => (
                    <div
                      key={group.group_id}
                      data-testid={`duplicate-group-${group.group_id}`}
                      className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                        selectedGroup?.group_id === group.group_id
                          ? 'border-cyan-500 bg-cyan-50'
                          : 'border-slate-200 hover:border-slate-300'
                      }`}
                      onClick={() => handleSelectGroup(group)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <Badge variant="outline" className="text-amber-700 border-amber-300 bg-amber-50">
                          {group.match_type === 'email' ? 'Email' : group.match_type}
                        </Badge>
                        <Badge 
                          variant={group.count > 2 ? "destructive" : "secondary"}
                          className={group.count > 2 ? "" : ""}
                        >
                          {group.count} registros
                        </Badge>
                      </div>
                      <p className="text-sm font-medium text-slate-900 truncate">
                        {group.match_value}
                      </p>
                      <p className="text-xs text-slate-500 mt-1">
                        {group.candidates[0]?.full_name}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Detail / Preview */}
          <Card>
            <CardHeader>
              <CardTitle>Detalle del Grupo</CardTitle>
              <CardDescription>
                Selecciona el registro principal y fusiona los demás
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!selectedGroup ? (
                <div className="text-center py-8 text-slate-500">
                  <Eye className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                  <p>Selecciona un grupo para ver el detalle</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Info banner for 3+ candidates */}
                  {selectedGroup.candidates.length > 2 && (
                    <Alert className="bg-blue-50 border-blue-200">
                      <Info className="w-4 h-4 text-blue-600" />
                      <AlertDescription className="text-blue-800">
                        Este grupo tiene <strong>{selectedGroup.candidates.length}</strong> registros.
                        Selecciona cuál será el principal y todos los demás se fusionarán en él.
                      </AlertDescription>
                    </Alert>
                  )}

                  {/* Candidates selection */}
                  <div className="space-y-2 max-h-[300px] overflow-y-auto">
                    {selectedGroup.candidates.map((candidate) => (
                      <div
                        key={candidate.id}
                        data-testid={`candidate-option-${candidate.id}`}
                        className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                          primaryCandidateId === candidate.id
                            ? 'border-green-500 bg-green-50 ring-2 ring-green-200'
                            : 'border-slate-200 hover:border-slate-300'
                        }`}
                        onClick={() => setPrimaryCandidateId(candidate.id)}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-medium text-slate-900">
                            {candidate.full_name}
                          </span>
                          {primaryCandidateId === candidate.id ? (
                            <Badge className="bg-green-600">Principal</Badge>
                          ) : (
                            <Badge variant="outline" className="text-slate-500">
                              Se fusionará
                            </Badge>
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-sm text-slate-600">
                          <div className="flex items-center gap-1">
                            <Briefcase className="w-3 h-3" />
                            <span className="truncate">{candidate.current_title || 'Sin título'}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {formatDate(candidate.created_at)}
                          </div>
                        </div>
                        {candidate.email && (
                          <div className="flex items-center gap-1 text-xs text-slate-500 mt-1">
                            <Mail className="w-3 h-3" />
                            {candidate.email}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Merge Button */}
                  <Button 
                    className="w-full" 
                    onClick={() => setMergeDialogOpen(true)}
                    disabled={!primaryCandidateId}
                    data-testid="open-merge-dialog-btn"
                  >
                    <Merge className="w-4 h-4 mr-2" />
                    Fusionar {selectedGroup.candidates.length} Candidatos
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Merge Dialog */}
        <Dialog open={mergeDialogOpen} onOpenChange={setMergeDialogOpen}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Confirmar Fusión de Candidatos</DialogTitle>
              <DialogDescription>
                {selectedGroup?.candidates.length > 2 
                  ? `Se fusionarán ${selectedGroup?.candidates.length - 1} registros en el principal`
                  : 'Se fusionará el registro secundario en el principal'
                }
              </DialogDescription>
            </DialogHeader>

            {selectedGroup && primaryCandidateId && (
              <div className="space-y-4">
                {/* Primary candidate info */}
                <div className="p-3 border border-green-300 bg-green-50 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <CheckCircle2 className="w-4 h-4 text-green-600" />
                    <span className="font-medium text-green-800">Registro Principal</span>
                  </div>
                  <p className="text-sm text-green-700">
                    {getPrimaryCandidate()?.full_name}
                  </p>
                  <p className="text-xs text-green-600">
                    {getPrimaryCandidate()?.email || 'Sin email'}
                  </p>
                </div>

                {/* Secondary candidates */}
                <div className="p-3 border border-amber-300 bg-amber-50 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <ArrowRight className="w-4 h-4 text-amber-600" />
                    <span className="font-medium text-amber-800">
                      Se fusionarán ({getSecondaryCandidates().length})
                    </span>
                  </div>
                  <ul className="text-sm text-amber-700 space-y-1">
                    {getSecondaryCandidates().map(c => (
                      <li key={c.id} className="truncate">
                        • {c.full_name}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Merge options */}
                <div className="space-y-3">
                  <Label>Opciones de Fusión</Label>
                  {[
                    { key: 'merge_experience', label: 'Combinar experiencia laboral' },
                    { key: 'merge_education', label: 'Combinar educación' },
                    { key: 'merge_skills', label: 'Combinar skills' },
                    { key: 'merge_notes', label: 'Combinar notas' },
                    { key: 'keep_all_cvs', label: 'Conservar todos los CVs como versiones' },
                  ].map(({ key, label }) => (
                    <div key={key} className="flex items-center space-x-2">
                      <Checkbox
                        id={key}
                        checked={mergeOptions[key]}
                        onCheckedChange={(checked) => 
                          setMergeOptions(prev => ({ ...prev, [key]: checked }))
                        }
                      />
                      <Label htmlFor={key} className="text-sm cursor-pointer">
                        {label}
                      </Label>
                    </div>
                  ))}
                </div>

                {/* Warning */}
                <Alert className="bg-slate-50">
                  <AlertCircle className="w-4 h-4" />
                  <AlertDescription>
                    Los registros secundarios serán marcados como eliminados pero se conservará el historial para auditoría.
                  </AlertDescription>
                </Alert>
              </div>
            )}

            <DialogFooter>
              <Button variant="outline" onClick={() => setMergeDialogOpen(false)}>
                Cancelar
              </Button>
              <Button 
                onClick={handleMerge} 
                disabled={merging || !primaryCandidateId}
                data-testid="confirm-merge-btn"
              >
                {merging ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Fusionando...
                  </>
                ) : (
                  <>
                    <Merge className="w-4 h-4 mr-2" />
                    Confirmar Fusión
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Orphan Records Dialog */}
        <Dialog open={orphanDialogOpen} onOpenChange={setOrphanDialogOpen}>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
            <DialogHeader>
              <DialogTitle>Registros Huérfanos</DialogTitle>
              <DialogDescription>
                Registros incompletos de cargas fallidas que pueden ser eliminados
              </DialogDescription>
            </DialogHeader>

            <div className="flex-1 overflow-y-auto">
              {loadingOrphans ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-8 h-8 animate-spin text-cyan-600" />
                </div>
              ) : orphanRecords ? (
                <div className="space-y-4">
                  {/* Summary */}
                  <div className="grid grid-cols-4 gap-2 text-center">
                    <div className="p-2 bg-slate-100 rounded">
                      <p className="text-lg font-bold">{orphanRecords.total_orphans}</p>
                      <p className="text-xs text-slate-500">Total</p>
                    </div>
                    <div className="p-2 bg-red-50 rounded">
                      <p className="text-lg font-bold text-red-600">{orphanRecords.by_category?.no_contact_info || 0}</p>
                      <p className="text-xs text-slate-500">Sin contacto</p>
                    </div>
                    <div className="p-2 bg-amber-50 rounded">
                      <p className="text-lg font-bold text-amber-600">{orphanRecords.by_category?.no_resume || 0}</p>
                      <p className="text-xs text-slate-500">Sin CV</p>
                    </div>
                    <div className="p-2 bg-orange-50 rounded">
                      <p className="text-lg font-bold text-orange-600">{orphanRecords.by_category?.generic_name || 0}</p>
                      <p className="text-xs text-slate-500">Nombre genérico</p>
                    </div>
                  </div>

                  {orphanRecords.orphans?.length === 0 ? (
                    <div className="text-center py-8 text-slate-500">
                      <CheckCircle2 className="w-12 h-12 mx-auto mb-3 text-green-500" />
                      <p>No hay registros huérfanos</p>
                    </div>
                  ) : (
                    <>
                      {/* Select all button */}
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-slate-500">
                          {selectedOrphans.length} seleccionados
                        </span>
                        <Button variant="ghost" size="sm" onClick={selectAllOrphans}>
                          Seleccionar todos
                        </Button>
                      </div>

                      {/* Orphan list */}
                      <div className="space-y-2 max-h-[300px] overflow-y-auto">
                        {orphanRecords.orphans?.map((orphan) => (
                          <div
                            key={orphan.id}
                            className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                              selectedOrphans.includes(orphan.id)
                                ? 'border-red-300 bg-red-50'
                                : 'border-slate-200'
                            }`}
                            onClick={() => toggleOrphanSelection(orphan.id)}
                          >
                            <div className="flex items-center gap-3">
                              <Checkbox 
                                checked={selectedOrphans.includes(orphan.id)}
                                onCheckedChange={() => toggleOrphanSelection(orphan.id)}
                              />
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-slate-900 truncate">
                                  {orphan.full_name || 'Sin nombre'}
                                </p>
                                <p className="text-xs text-slate-500">
                                  {orphan.email || 'Sin email'} • {formatDate(orphan.created_at)}
                                </p>
                              </div>
                              {!orphan.resume_files?.length && (
                                <Badge variant="outline" className="text-amber-600 border-amber-300">
                                  Sin CV
                                </Badge>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              ) : (
                <div className="text-center py-8 text-slate-500">
                  <AlertCircle className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                  <p>Error cargando datos</p>
                </div>
              )}
            </div>

            <DialogFooter className="border-t pt-4">
              <Button variant="outline" onClick={() => setOrphanDialogOpen(false)}>
                Cerrar
              </Button>
              <Button 
                variant="destructive"
                onClick={handleCleanupOrphans}
                disabled={cleaningOrphans || selectedOrphans.length === 0}
              >
                {cleaningOrphans ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Eliminando...
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4 mr-2" />
                    Eliminar {selectedOrphans.length} Registros
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};

export default DuplicatesPage;
