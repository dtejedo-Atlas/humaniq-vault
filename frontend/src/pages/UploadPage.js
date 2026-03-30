import React, { useState, useCallback, useEffect, useRef } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Switch } from '../components/ui/switch';
import { Label } from '../components/ui/label';
import { useDropzone } from 'react-dropzone';
import { 
  Upload, FileText, CheckCircle, AlertCircle, Loader2, 
  AlertTriangle, Clock, RefreshCw, X, Play, Pause,
  ChevronDown, ChevronUp
} from 'lucide-react';
import { candidatesAPI } from '../api';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

// Mapeo de etapas a nombres legibles
const STAGE_LABELS = {
  queued: 'En cola',
  upload: 'Carga',
  storage: 'Almacenamiento',
  text_extraction: 'Extracción de texto',
  ai_parsing: 'Parsing con IA',
  ai_classification: 'Clasificación IA',
  creating_candidate: 'Creando candidato',
  embedding_generation: 'Búsqueda semántica',
  duplicate_detection: 'Detección de duplicados',
  database_save: 'Guardado en DB',
  completed: 'Completado'
};

const UploadPage = () => {
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);
  const [useBatchMode, setUseBatchMode] = useState(true);
  const [currentBatchId, setCurrentBatchId] = useState(null);
  const [batchStatus, setBatchStatus] = useState(null);
  const [uploadResults, setUploadResults] = useState([]);
  const [expandedJobs, setExpandedJobs] = useState({});
  const pollIntervalRef = useRef(null);

  // Polling para actualizar estado del batch
  useEffect(() => {
    if (currentBatchId && useBatchMode) {
      pollIntervalRef.current = setInterval(async () => {
        try {
          const response = await candidatesAPI.getBatchStatus(currentBatchId);
          setBatchStatus(response.data);
          
          // Detener polling si el batch está completo
          if (response.data.is_complete) {
            clearInterval(pollIntervalRef.current);
            setUploading(false);
            toast.success('Procesamiento de lote completado');
          }
        } catch (error) {
          console.error('Error polling batch status:', error);
        }
      }, 1500); // Poll cada 1.5 segundos
    }
    
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [currentBatchId, useBatchMode]);

  // Limpieza al desmontar
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return;
    
    setUploading(true);
    
    if (useBatchMode && acceptedFiles.length > 1) {
      // MODO BATCH: Subir todos y procesar en background
      try {
        const response = await candidatesAPI.uploadBatch(acceptedFiles);
        setCurrentBatchId(response.data.batch_id);
        setBatchStatus(null); // Reset status
        
        toast.info(`${response.data.queued} archivos en cola para procesamiento`);
        
        if (response.data.rejected > 0) {
          toast.warning(`${response.data.rejected} archivos rechazados`);
        }
      } catch (error) {
        toast.error('Error iniciando carga de lote');
        setUploading(false);
      }
    } else {
      // MODO INDIVIDUAL: Procesar uno por uno (comportamiento original)
      const results = [];

      for (const file of acceptedFiles) {
        try {
          const response = await candidatesAPI.uploadResume(file);
          const data = response.data;
          
          const status = data.status || 'unknown';
          const isSuccess = status === 'success';
          const isPartialSuccess = status === 'partial_success';
          const isDuplicate = status === 'duplicate_detected';
          
          results.push({
            fileName: file.name,
            status: status,
            success: isSuccess || isPartialSuccess,
            candidateId: data.candidate_id,
            candidateName: data.extracted_name || data.parsed_data?.full_name || 'Desconocido',
            extractedEmail: data.extracted_email,
            stageReached: data.stage_reached,
            errors: data.errors || [],
            warnings: data.warnings || [],
            processingTime: data.processing_time_ms,
            duplicates: data.duplicates,
            isDuplicate
          });
          
          if (isSuccess) {
            toast.success(`CV procesado: ${file.name}`);
          } else if (isPartialSuccess) {
            toast.warning(`CV procesado con advertencias: ${file.name}`);
          } else if (isDuplicate) {
            toast.info(`Posible duplicado detectado: ${file.name}`);
          } else {
            toast.error(`Error procesando ${file.name}`);
          }
        } catch (error) {
          results.push({
            fileName: file.name,
            status: 'error',
            success: false,
            errors: [{
              type: 'network_error',
              stage: 'upload',
              message: error.response?.data?.detail || error.message || 'Error de conexión'
            }]
          });
          toast.error(`Error procesando ${file.name}`);
        }
      }

      setUploadResults(results);
      setUploading(false);
    }
  }, [useBatchMode]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx']
      // .doc (Word 97-2003) NO soportado - solo PDF y DOCX
    },
    disabled: uploading
  });

  const handleRetryJob = async (jobId) => {
    try {
      await candidatesAPI.retryJob(jobId);
      toast.success('Job re-encolado para reintento');
    } catch (error) {
      toast.error('Error al reintentar job');
    }
  };

  const toggleJobExpand = (jobId) => {
    setExpandedJobs(prev => ({
      ...prev,
      [jobId]: !prev[jobId]
    }));
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'completed':
      case 'success':
        return <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">Exitoso</Badge>;
      case 'partial':
      case 'partial_success':
        return <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">Parcial</Badge>;
      case 'processing':
        return <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">Procesando</Badge>;
      case 'pending':
      case 'queued':
        return <Badge variant="outline" className="bg-gray-50 text-gray-700 border-gray-200">En cola</Badge>;
      case 'failed':
      case 'error':
        return <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">Fallido</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'partial':
      case 'partial_success':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      case 'processing':
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'pending':
      case 'queued':
        return <Clock className="w-5 h-5 text-gray-400" />;
      default:
        return <AlertCircle className="w-5 h-5 text-red-500" />;
    }
  };

  const resetUpload = () => {
    setCurrentBatchId(null);
    setBatchStatus(null);
    setUploadResults([]);
    setExpandedJobs({});
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }
  };

  // Calcular estadísticas
  const stats = batchStatus?.stats || {
    pending: 0,
    processing: 0,
    completed: 0,
    partial: 0,
    failed: 0
  };

  const totalProcessed = stats.completed + stats.partial + stats.failed;
  const totalJobs = batchStatus?.total_files || 0;
  const overallProgress = totalJobs > 0 ? Math.round((totalProcessed / totalJobs) * 100) : 0;

  return (
    <Layout title="Subir CVs" subtitle="Carga currículums para procesarlos con Humaniq IA">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Upload Zone */}
        <Card>
          <CardHeader>
            <div className="flex justify-between items-start">
              <div>
                <CardTitle>Cargar Currículums</CardTitle>
                <CardDescription>
                  Arrastra y suelta archivos PDF o DOCX, o haz clic para seleccionar.
                </CardDescription>
              </div>
              <div className="flex items-center space-x-2">
                <Switch
                  id="batch-mode"
                  checked={useBatchMode}
                  onCheckedChange={setUseBatchMode}
                  disabled={uploading}
                />
                <Label htmlFor="batch-mode" className="text-sm">
                  Modo Lote (paralelo)
                </Label>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div
              {...getRootProps()}
              data-testid="upload-dropzone"
              className={`
                upload-zone border-2 border-dashed rounded-sm p-12 text-center cursor-pointer
                ${isDragActive ? 'border-cyan-500 bg-cyan-50' : 'border-slate-300'}
                ${uploading ? 'opacity-50 cursor-not-allowed' : 'hover:border-cyan-400'}
              `}
            >
              <input {...getInputProps()} />
              
              <div className="flex flex-col items-center gap-4">
                <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center">
                  {uploading ? (
                    <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
                  ) : (
                    <Upload className="w-8 h-8 text-slate-600" />
                  )}
                </div>
                
                <div>
                  <p className="text-lg font-medium text-slate-900">
                    {isDragActive 
                      ? 'Suelta los archivos aquí' 
                      : uploading
                      ? 'Procesando archivos...'
                      : 'Arrastra archivos o haz clic para seleccionar'}
                  </p>
                  <p className="text-sm text-slate-500 mt-1">
                    PDF, DOCX • Máx 50 archivos • Máx 10MB por archivo
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    Nota: Archivos .doc (Word antiguo) no soportados
                  </p>
                  {useBatchMode && (
                    <p className="text-xs text-cyan-600 mt-2">
                      Modo Lote: Los archivos se procesan en paralelo en background
                    </p>
                  )}
                </div>
                
                {!uploading && (
                  <Button variant="outline" className="mt-2">
                    Seleccionar Archivos
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Batch Progress (Modo Lote) */}
        {useBatchMode && currentBatchId && (
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle>Progreso del Lote</CardTitle>
                  <CardDescription>
                    {totalProcessed} de {totalJobs} archivos procesados
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  {batchStatus?.is_complete && (
                    <Button variant="outline" size="sm" onClick={resetUpload}>
                      <X className="w-4 h-4 mr-1" />
                      Cerrar
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {/* Progress bar general */}
              <div className="mb-4">
                <Progress value={overallProgress} className="h-2" />
                <div className="flex justify-between text-xs text-slate-500 mt-1">
                  <span>{overallProgress}% completado</span>
                  <div className="flex gap-3">
                    <span className="text-green-600">{stats.completed} exitosos</span>
                    {stats.partial > 0 && <span className="text-yellow-600">{stats.partial} parciales</span>}
                    {stats.failed > 0 && <span className="text-red-600">{stats.failed} fallidos</span>}
                    {stats.processing > 0 && <span className="text-blue-600">{stats.processing} procesando</span>}
                    {stats.pending > 0 && <span className="text-gray-500">{stats.pending} en cola</span>}
                  </div>
                </div>
              </div>

              {/* Lista de jobs */}
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {batchStatus?.jobs?.map((job) => (
                  <div
                    key={job.job_id}
                    className={`p-3 border rounded-sm ${
                      job.status === 'completed' ? 'border-green-200 bg-green-50/50' :
                      job.status === 'partial' ? 'border-yellow-200 bg-yellow-50/50' :
                      job.status === 'processing' ? 'border-blue-200 bg-blue-50/50' :
                      job.status === 'failed' ? 'border-red-200 bg-red-50/50' :
                      'border-slate-200'
                    }`}
                  >
                    {/* Header del job */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 flex-1">
                        <FileText className="w-4 h-4 text-slate-400" />
                        <span className="text-sm font-medium truncate">{job.file_name}</span>
                        {job.extracted_name && job.extracted_name !== job.file_name && (
                          <span className="text-xs text-slate-500">→ {job.extracted_name}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {job.status === 'processing' && (
                          <span className="text-xs text-blue-600">{job.progress}%</span>
                        )}
                        {getStatusBadge(job.status)}
                        {getStatusIcon(job.status)}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0"
                          onClick={() => toggleJobExpand(job.job_id)}
                        >
                          {expandedJobs[job.job_id] ? (
                            <ChevronUp className="w-4 h-4" />
                          ) : (
                            <ChevronDown className="w-4 h-4" />
                          )}
                        </Button>
                      </div>
                    </div>
                    
                    {/* Barra de progreso individual */}
                    {job.status === 'processing' && (
                      <div className="mt-2">
                        <Progress value={job.progress} className="h-1" />
                        <span className="text-xs text-slate-500">{STAGE_LABELS[job.current_stage] || job.current_stage}</span>
                      </div>
                    )}
                    
                    {/* Detalles expandidos */}
                    {expandedJobs[job.job_id] && (
                      <div className="mt-2 pt-2 border-t border-slate-200">
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <span className="text-slate-500">Etapa:</span>{' '}
                            <span>{STAGE_LABELS[job.current_stage] || job.current_stage}</span>
                          </div>
                          {job.processing_time_ms && (
                            <div>
                              <span className="text-slate-500">Tiempo:</span>{' '}
                              <span>{job.processing_time_ms}ms</span>
                            </div>
                          )}
                          {job.extracted_email && (
                            <div>
                              <span className="text-slate-500">Email:</span>{' '}
                              <span>{job.extracted_email}</span>
                            </div>
                          )}
                          {job.retry_count > 0 && (
                            <div>
                              <span className="text-slate-500">Reintentos:</span>{' '}
                              <span>{job.retry_count}</span>
                            </div>
                          )}
                        </div>
                        
                        {/* Errores */}
                        {job.errors && job.errors.length > 0 && (
                          <div className="mt-2 space-y-1">
                            {job.errors.map((error, idx) => (
                              <div key={idx} className="text-xs p-2 bg-red-100 text-red-700 rounded">
                                [{STAGE_LABELS[error.stage] || error.stage}] {error.message}
                              </div>
                            ))}
                          </div>
                        )}
                        
                        {/* Warnings */}
                        {job.warnings && job.warnings.length > 0 && (
                          <div className="mt-2 space-y-1">
                            {job.warnings.map((warning, idx) => (
                              <div key={idx} className="text-xs p-2 bg-yellow-100 text-yellow-700 rounded">
                                {warning}
                              </div>
                            ))}
                          </div>
                        )}
                        
                        {/* Acciones */}
                        <div className="mt-2 flex gap-2">
                          {job.candidate_id && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => navigate(`/candidates/${job.candidate_id}`)}
                            >
                              Ver Perfil
                            </Button>
                          )}
                          {(job.status === 'failed' || job.status === 'partial') && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleRetryJob(job.job_id)}
                            >
                              <RefreshCw className="w-3 h-3 mr-1" />
                              Reintentar
                            </Button>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
              
              {batchStatus?.is_complete && (
                <div className="mt-4 flex gap-3">
                  <Button
                    onClick={() => navigate('/candidates')}
                    className="flex-1"
                  >
                    Ver Todos los Candidatos
                  </Button>
                  <Button
                    variant="outline"
                    onClick={resetUpload}
                  >
                    Cargar Más
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Upload Results (Modo Individual) */}
        {!useBatchMode && uploadResults.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Resultados de Carga</CardTitle>
              <CardDescription>
                <div className="flex gap-4 mt-2">
                  <span className="text-green-600">{uploadResults.filter(r => r.status === 'success').length} exitosos</span>
                  {uploadResults.filter(r => r.status === 'partial_success').length > 0 && (
                    <span className="text-yellow-600">{uploadResults.filter(r => r.status === 'partial_success').length} parciales</span>
                  )}
                  {uploadResults.filter(r => r.status === 'failed' || r.status === 'error').length > 0 && (
                    <span className="text-red-600">{uploadResults.filter(r => r.status === 'failed' || r.status === 'error').length} fallidos</span>
                  )}
                </div>
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {uploadResults.map((result, index) => (
                  <div
                    key={index}
                    className={`p-4 border rounded-sm ${
                      result.status === 'success' ? 'border-green-200 bg-green-50/50' :
                      result.status === 'partial_success' ? 'border-yellow-200 bg-yellow-50/50' :
                      'border-red-200 bg-red-50/50'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-slate-400" />
                        <span className="text-sm font-medium">{result.fileName}</span>
                        {result.candidateName && (
                          <span className="text-xs text-slate-500">→ {result.candidateName}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {getStatusBadge(result.status)}
                        {getStatusIcon(result.status)}
                      </div>
                    </div>
                    
                    {result.candidateId && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="mt-2"
                        onClick={() => navigate(`/candidates/${result.candidateId}`)}
                      >
                        Ver Perfil
                      </Button>
                    )}
                  </div>
                ))}
              </div>
              
              <div className="mt-6 flex gap-3">
                <Button onClick={() => navigate('/candidates')} className="flex-1">
                  Ver Todos los Candidatos
                </Button>
                <Button variant="outline" onClick={() => setUploadResults([])}>
                  Cargar Más
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Instructions */}
        <Card>
          <CardHeader>
            <CardTitle>Cómo Funciona Humaniq IA</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="text-center">
                <div className="w-12 h-12 bg-cyan-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  <span className="text-xl font-bold text-cyan-600">1</span>
                </div>
                <h3 className="font-semibold text-slate-900 mb-2">Carga el CV</h3>
                <p className="text-sm text-slate-600">
                  Sube currículums en PDF o DOCX. En modo lote, procesa hasta 50 archivos en paralelo.
                </p>
              </div>
              
              <div className="text-center">
                <div className="w-12 h-12 bg-cyan-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  <span className="text-xl font-bold text-cyan-600">2</span>
                </div>
                <h3 className="font-semibold text-slate-900 mb-2">Humaniq Analiza</h3>
                <p className="text-sm text-slate-600">
                  La IA extrae datos y clasifica por industria, área funcional y seniority.
                </p>
              </div>
              
              <div className="text-center">
                <div className="w-12 h-12 bg-cyan-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  <span className="text-xl font-bold text-cyan-600">3</span>
                </div>
                <h3 className="font-semibold text-slate-900 mb-2">Revisa y Aprueba</h3>
                <p className="text-sm text-slate-600">
                  Revisa errores detallados, reintenta fallidos y aprueba perfiles.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

export default UploadPage;
