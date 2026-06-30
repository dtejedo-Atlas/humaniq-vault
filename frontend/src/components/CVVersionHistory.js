import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Alert, AlertDescription } from './ui/alert';
import {
  FileText,
  Download,
  Upload,
  History,
  ChevronDown,
  ChevronUp,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Clock,
  User,
  GitCompare
} from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

const CVVersionHistory = ({ candidateId, candidateName, onVersionUpdated }) => {
  const [loading, setLoading] = useState(true);
  const [versions, setVersions] = useState([]);
  const [expanded, setExpanded] = useState(false);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadNotes, setUploadNotes] = useState('');
  const [compareDialogOpen, setCompareDialogOpen] = useState(false);
  const [comparison, setComparison] = useState(null);
  const [comparing, setComparing] = useState(false);
  const [selectedVersions, setSelectedVersions] = useState([]);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (candidateId) {
      loadVersions();
    }
  }, [candidateId]);

  const loadVersions = async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/candidates/${candidateId}/cv-versions`);
      setVersions(res.data.versions || []);
    } catch (error) {
      console.error('Error loading CV versions:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!['pdf', 'docx'].includes(ext)) {
      toast.error('Solo se permiten archivos PDF o DOCX');
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      toast.error('El archivo excede el límite de 10MB');
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (uploadNotes) {
        formData.append('notes', uploadNotes);
      }

      const res = await axios.post(
        `${API_BASE}/api/candidates/${candidateId}/update-cv`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );

      toast.success(`CV actualizado (versión ${res.data.version})`);
      setUploadDialogOpen(false);
      setUploadNotes('');
      loadVersions();
      
      if (onVersionUpdated) {
        onVersionUpdated(res.data);
      }
    } catch (error) {
      console.error('Error uploading CV:', error);
      toast.error(error.response?.data?.detail || 'Error subiendo CV');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDownload = async (version) => {
    try {
      const res = await axios.get(
        `${API_BASE}/api/candidates/${candidateId}/cv-versions/${version.version}/download`,
        { responseType: 'blob' }
      );
      
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', version.file_name);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error downloading CV:', error);
      toast.error('Error descargando CV');
    }
  };

  const handleCompare = async () => {
    if (selectedVersions.length !== 2) {
      toast.error('Selecciona exactamente 2 versiones para comparar');
      return;
    }

    setComparing(true);
    try {
      const [v1, v2] = selectedVersions.sort((a, b) => a - b);
      const res = await axios.get(
        `${API_BASE}/api/candidates/${candidateId}/cv-versions/${v1}/compare/${v2}`
      );
      setComparison(res.data);
      setCompareDialogOpen(true);
    } catch (error) {
      console.error('Error comparing versions:', error);
      toast.error('Error comparando versiones');
    } finally {
      setComparing(false);
    }
  };

  const toggleVersionSelection = (versionNum) => {
    setSelectedVersions(prev => {
      if (prev.includes(versionNum)) {
        return prev.filter(v => v !== versionNum);
      }
      if (prev.length >= 2) {
        return [prev[1], versionNum];
      }
      return [...prev, versionNum];
    });
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('es-MX', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getSourceBadge = (source) => {
    const styles = {
      manual: 'bg-blue-100 text-blue-800',
      update: 'bg-green-100 text-green-800',
      merge: 'bg-purple-100 text-purple-800',
      migration: 'bg-gray-100 text-gray-800'
    };
    const labels = {
      manual: 'Manual',
      update: 'Actualización',
      merge: 'Merge',
      migration: 'Migración'
    };
    return (
      <Badge className={styles[source] || styles.manual} variant="outline">
        {labels[source] || source}
      </Badge>
    );
  };

  if (loading) {
    return (
      <Card className="border-2 border-cyan-200 shadow-md">
        <CardContent className="py-4 flex items-center justify-center">
          <Loader2 className="w-5 h-5 animate-spin text-cyan-600" />
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card className="border-2 border-cyan-200 shadow-md overflow-hidden">
        <CardHeader 
          className="py-4 px-4 cursor-pointer bg-gradient-to-r from-cyan-600 to-blue-600 text-white" 
          onClick={() => setExpanded(!expanded)}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-white/20 rounded-lg">
                <History className="w-5 h-5 text-white" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold text-white">
                  Historial de CVs
                </CardTitle>
                <p className="text-cyan-100 text-sm">
                  {versions.length} {versions.length === 1 ? 'versión guardada' : 'versiones guardadas'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                className="bg-white/20 hover:bg-white/30 text-white border-0"
                onClick={(e) => {
                  e.stopPropagation();
                  setUploadDialogOpen(true);
                }}
              >
                <Upload className="w-4 h-4 mr-1" />
                Nueva versión
              </Button>
              {expanded ? (
                <ChevronUp className="w-5 h-5 text-white/80" />
              ) : (
                <ChevronDown className="w-5 h-5 text-white/80" />
              )}
            </div>
          </div>
        </CardHeader>

        {expanded && (
          <CardContent className="pt-4 pb-4 bg-white">
            {versions.length === 0 ? (
              <div className="text-center py-6 text-slate-500">
                <FileText className="w-10 h-10 mx-auto mb-2 text-slate-300" />
                <p className="text-sm">No hay versiones de CV registradas</p>
                <p className="text-xs text-slate-400 mt-1">
                  Sube un CV para crear la primera versión
                </p>
              </div>
            ) : (
              <>
                {versions.length > 1 && (
                  <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-200">
                    <span className="text-xs text-slate-500">
                      {selectedVersions.length === 2 
                        ? `Comparando v${selectedVersions[0]} con v${selectedVersions[1]}`
                        : 'Selecciona 2 versiones para comparar'}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={selectedVersions.length !== 2 || comparing}
                      onClick={handleCompare}
                    >
                      {comparing ? (
                        <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                      ) : (
                        <GitCompare className="w-3.5 h-3.5 mr-1" />
                      )}
                      Comparar
                    </Button>
                  </div>
                )}

                <div className="space-y-3">
                  {versions.map((version) => (
                    <div
                      key={version.id}
                      data-testid={`cv-version-${version.version}`}
                      className={`p-4 rounded-lg border-2 transition-all ${
                        version.is_current 
                          ? 'bg-cyan-50 border-cyan-300 shadow-sm' 
                          : selectedVersions.includes(version.version)
                            ? 'bg-slate-100 border-slate-400'
                            : 'bg-white border-slate-200 hover:border-slate-300 hover:shadow-sm'
                      }`}
                      onClick={() => versions.length > 1 && toggleVersionSelection(version.version)}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-3 flex-1 min-w-0">
                          {versions.length > 1 && (
                            <input
                              type="checkbox"
                              checked={selectedVersions.includes(version.version)}
                              onChange={() => toggleVersionSelection(version.version)}
                              onClick={(e) => e.stopPropagation()}
                              className="rounded border-slate-300 mt-1"
                            />
                          )}
                          <div className={`p-2 rounded-lg ${version.is_current ? 'bg-cyan-100' : 'bg-slate-100'}`}>
                            <FileText className={`w-5 h-5 ${version.is_current ? 'text-cyan-600' : 'text-slate-500'}`} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-semibold text-slate-900">
                                Versión {version.version}
                              </span>
                              {version.is_current && (
                                <Badge className="bg-cyan-600 text-white text-xs">
                                  <CheckCircle2 className="w-3 h-3 mr-1" />
                                  Actual
                                </Badge>
                              )}
                              {getSourceBadge(version.upload_source)}
                            </div>
                            <p className="text-sm text-slate-600 truncate mt-1">
                              {version.file_name}
                            </p>
                            <div className="flex items-center gap-4 text-xs text-slate-500 mt-2">
                              <span className="flex items-center gap-1">
                                <Clock className="w-3.5 h-3.5" />
                                {formatDate(version.uploaded_at || version.created_at)}
                              </span>
                              <span className="flex items-center gap-1">
                                <User className="w-3.5 h-3.5" />
                                {version.uploaded_by_name || 'Sistema'}
                              </span>
                              {version.file_size && (
                                <span>{formatFileSize(version.file_size)}</span>
                              )}
                            </div>
                            {version.notes && (
                              <p className="text-xs text-slate-500 mt-2 italic bg-slate-50 p-2 rounded">
                                &ldquo;{version.notes}&rdquo;
                              </p>
                            )}
                          </div>
                        </div>
                        <Button
                          variant="default"
                          size="sm"
                          className="bg-cyan-600 hover:bg-cyan-700 text-white shrink-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDownload(version);
                          }}
                          data-testid={`download-cv-v${version.version}`}
                        >
                          <Download className="w-4 h-4 mr-1" />
                          Descargar
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        )}
      </Card>

      {/* Upload Dialog */}
      <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Subir Nueva Versión de CV</DialogTitle>
            <DialogDescription>
              Sube un CV actualizado para {candidateName}. Se guardará como una nueva versión.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Archivo (PDF o DOCX)</Label>
              <Input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx"
                onChange={handleFileSelect}
                disabled={uploading}
              />
            </div>

            <div className="space-y-2">
              <Label>Notas (opcional)</Label>
              <Textarea
                placeholder="Ej: CV actualizado post-promoción a Director..."
                value={uploadNotes}
                onChange={(e) => setUploadNotes(e.target.value)}
                disabled={uploading}
              />
            </div>

            {uploading && (
              <Alert>
                <Loader2 className="w-4 h-4 animate-spin" />
                <AlertDescription>
                  Subiendo y procesando CV...
                </AlertDescription>
              </Alert>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setUploadDialogOpen(false)} disabled={uploading}>
              Cancelar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Compare Dialog */}
      <Dialog open={compareDialogOpen} onOpenChange={setCompareDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Comparación de Versiones</DialogTitle>
            <DialogDescription>
              Diferencias entre v{comparison?.version1?.version} y v{comparison?.version2?.version}
            </DialogDescription>
          </DialogHeader>

          {comparison && (
            <div className="space-y-4">
              {/* Version info */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="p-3 bg-slate-50 rounded-lg">
                  <p className="font-medium">Versión {comparison.version1.version}</p>
                  <p className="text-slate-500 text-xs">{formatDate(comparison.version1.uploaded_at)}</p>
                  <p className="text-slate-500 text-xs">Por: {comparison.version1.uploaded_by_name}</p>
                </div>
                <div className="p-3 bg-slate-50 rounded-lg">
                  <p className="font-medium">Versión {comparison.version2.version}</p>
                  <p className="text-slate-500 text-xs">{formatDate(comparison.version2.uploaded_at)}</p>
                  <p className="text-slate-500 text-xs">Por: {comparison.version2.uploaded_by_name}</p>
                </div>
              </div>

              {/* Alerts */}
              {comparison.alerts?.length > 0 && (
                <div className="space-y-2">
                  {comparison.alerts.map((alert, idx) => (
                    <Alert 
                      key={idx} 
                      className={
                        alert.type === 'high' 
                          ? 'bg-red-50 border-red-200' 
                          : 'bg-yellow-50 border-yellow-200'
                      }
                    >
                      <AlertTriangle className={`w-4 h-4 ${
                        alert.type === 'high' ? 'text-red-600' : 'text-yellow-600'
                      }`} />
                      <AlertDescription>
                        <strong>{alert.message}</strong>
                        {alert.details && (
                          <ul className="mt-1 text-sm">
                            {alert.details.map((d, i) => <li key={i}>• {d}</li>)}
                          </ul>
                        )}
                      </AlertDescription>
                    </Alert>
                  ))}
                </div>
              )}

              {/* Differences */}
              {comparison.differences?.length > 0 ? (
                <div className="space-y-2">
                  <h4 className="font-medium text-sm">Cambios Detectados ({comparison.total_differences})</h4>
                  {comparison.differences.map((diff, idx) => (
                    <div key={idx} className="p-3 border rounded-lg text-sm">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium">{diff.label}</span>
                        <Badge variant="outline" className={
                          diff.type === 'removed' ? 'text-red-600' :
                          diff.type === 'added' ? 'text-green-600' :
                          'text-blue-600'
                        }>
                          {diff.type === 'removed' ? 'Eliminado' :
                           diff.type === 'added' ? 'Agregado' : 'Modificado'}
                        </Badge>
                      </div>
                      {diff.version_old !== undefined && (
                        <div className="text-slate-500">
                          <span className="line-through text-red-600">{String(diff.version_old || 'N/A')}</span>
                          {' → '}
                          <span className="text-green-600">{String(diff.version_new || 'N/A')}</span>
                        </div>
                      )}
                      {diff.count && <span className="text-slate-500">{diff.count} item(s)</span>}
                      {diff.values && (
                        <span className="text-slate-500">{diff.values.join(', ')}</span>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <Alert className="bg-green-50 border-green-200">
                  <CheckCircle2 className="w-4 h-4 text-green-600" />
                  <AlertDescription>
                    No se detectaron diferencias significativas entre las versiones.
                  </AlertDescription>
                </Alert>
              )}
            </div>
          )}

          <DialogFooter>
            <Button onClick={() => setCompareDialogOpen(false)}>Cerrar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default CVVersionHistory;
