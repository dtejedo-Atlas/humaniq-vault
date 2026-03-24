import React, { useState, useCallback } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, CheckCircle, AlertCircle, Loader2, AlertTriangle, Clock, RefreshCw } from 'lucide-react';
import { candidatesAPI } from '../api';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

// Mapeo de etapas a nombres legibles
const STAGE_LABELS = {
  upload: 'Carga',
  storage: 'Almacenamiento',
  text_extraction: 'Extracción de texto',
  ai_parsing: 'Parsing con IA',
  ai_classification: 'Clasificación IA',
  embedding_generation: 'Búsqueda semántica',
  duplicate_detection: 'Detección de duplicados',
  database_save: 'Guardado en DB',
  completed: 'Completado'
};

// Mapeo de tipos de error a iconos y colores
const ERROR_SEVERITY = {
  unsupported_format: { color: 'red', icon: AlertCircle },
  file_corrupted: { color: 'red', icon: AlertCircle },
  file_empty: { color: 'red', icon: AlertCircle },
  pdf_scanned_no_ocr: { color: 'yellow', icon: AlertTriangle },
  no_text_extractable: { color: 'yellow', icon: AlertTriangle },
  ai_parsing_failed: { color: 'yellow', icon: AlertTriangle },
  ai_classification_failed: { color: 'yellow', icon: AlertTriangle },
  embedding_api_error: { color: 'gray', icon: AlertTriangle },
  validation_error: { color: 'red', icon: AlertCircle },
  database_save_failed: { color: 'red', icon: AlertCircle },
};

const UploadPage = () => {
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);
  const [uploadResults, setUploadResults] = useState([]);

  const onDrop = useCallback(async (acceptedFiles) => {
    setUploading(true);
    const results = [];

    for (const file of acceptedFiles) {
      try {
        const response = await candidatesAPI.uploadResume(file);
        const data = response.data;
        
        // Determinar estado basado en la respuesta del servidor
        const status = data.status || 'unknown';
        const isSuccess = status === 'success';
        const isPartialSuccess = status === 'partial_success';
        const isFailed = status === 'failed';
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
        // Error de red o servidor
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
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/msword': ['.doc']
    },
    disabled: uploading
  });

  const getStatusBadge = (result) => {
    if (result.isDuplicate) {
      return <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">Duplicado</Badge>;
    }
    switch (result.status) {
      case 'success':
        return <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">Exitoso</Badge>;
      case 'partial_success':
        return <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">Parcial</Badge>;
      case 'failed':
        return <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">Fallido</Badge>;
      default:
        return <Badge variant="outline" className="bg-gray-50 text-gray-700 border-gray-200">Error</Badge>;
    }
  };

  const getStatusIcon = (result) => {
    if (result.isDuplicate) return <AlertTriangle className="w-5 h-5 text-blue-500" />;
    switch (result.status) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'partial_success':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      default:
        return <AlertCircle className="w-5 h-5 text-red-500" />;
    }
  };

  // Calcular estadísticas
  const stats = {
    total: uploadResults.length,
    success: uploadResults.filter(r => r.status === 'success').length,
    partial: uploadResults.filter(r => r.status === 'partial_success').length,
    failed: uploadResults.filter(r => r.status === 'failed' || r.status === 'error').length,
    duplicates: uploadResults.filter(r => r.isDuplicate).length
  };

  return (
    <Layout title="Subir CVs" subtitle="Carga currículums para procesarlos con Atlas IA">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Upload Zone */}
        <Card>
          <CardHeader>
            <CardTitle>Cargar Currículums</CardTitle>
            <CardDescription>
              Arrastra y suelta archivos PDF o DOCX, o haz clic para seleccionar.
              Atlas IA extraerá y clasificará automáticamente la información.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              {...getRootProps()}
              data-testid="upload-dropzone"
              className={`
                upload-zone border-2 border-dashed rounded-sm p-12 text-center cursor-pointer
                ${isDragActive ? 'drag-active' : ''}
                ${uploading ? 'opacity-50 cursor-not-allowed' : ''}
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
                    Archivos permitidos: PDF, DOCX, DOC
                  </p>
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

        {/* Upload Results */}
        {uploadResults.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Resultados de Carga</CardTitle>
              <CardDescription>
                <div className="flex gap-4 mt-2">
                  <span className="text-green-600">{stats.success} exitosos</span>
                  {stats.partial > 0 && <span className="text-yellow-600">{stats.partial} parciales</span>}
                  {stats.failed > 0 && <span className="text-red-600">{stats.failed} fallidos</span>}
                  {stats.duplicates > 0 && <span className="text-blue-600">{stats.duplicates} duplicados</span>}
                </div>
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {uploadResults.map((result, index) => (
                  <div
                    key={index}
                    data-testid={`upload-result-${index}`}
                    className={`p-4 border rounded-sm ${
                      result.status === 'success' ? 'border-green-200 bg-green-50/50' :
                      result.status === 'partial_success' ? 'border-yellow-200 bg-yellow-50/50' :
                      result.isDuplicate ? 'border-blue-200 bg-blue-50/50' :
                      'border-red-200 bg-red-50/50'
                    }`}
                  >
                    {/* Header del resultado */}
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <FileText className="w-5 h-5 text-slate-400" />
                        <div>
                          <p className="text-sm font-medium text-slate-900">{result.fileName}</p>
                          {result.candidateName && result.candidateName !== 'Desconocido' && (
                            <p className="text-xs text-slate-600">
                              {result.candidateName}
                              {result.extractedEmail && ` • ${result.extractedEmail}`}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {getStatusBadge(result)}
                        {getStatusIcon(result)}
                      </div>
                    </div>
                    
                    {/* Tiempo de procesamiento */}
                    {result.processingTime && (
                      <div className="flex items-center gap-1 text-xs text-slate-500 mb-2">
                        <Clock className="w-3 h-3" />
                        <span>{result.processingTime}ms</span>
                        {result.stageReached && (
                          <span className="ml-2">• Etapa: {STAGE_LABELS[result.stageReached] || result.stageReached}</span>
                        )}
                      </div>
                    )}
                    
                    {/* Errores detallados */}
                    {result.errors && result.errors.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {result.errors.map((error, errIdx) => (
                          <div 
                            key={errIdx}
                            className={`text-xs p-2 rounded ${
                              error.type?.includes('api_error') || error.type?.includes('embedding') 
                                ? 'bg-gray-100 text-gray-700' 
                                : 'bg-red-100 text-red-700'
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              <span className="font-medium">[{STAGE_LABELS[error.stage] || error.stage}]</span>
                              <span>{error.message}</span>
                            </div>
                            {error.recoverable && (
                              <span className="text-xs text-gray-500 ml-4">• Recuperable</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    
                    {/* Advertencias */}
                    {result.warnings && result.warnings.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {result.warnings.map((warning, warnIdx) => (
                          <div 
                            key={warnIdx}
                            className="text-xs p-2 rounded bg-yellow-100 text-yellow-800"
                          >
                            {warning}
                          </div>
                        ))}
                      </div>
                    )}
                    
                    {/* Duplicados detectados */}
                    {result.isDuplicate && result.duplicates && (
                      <div className="mt-2 p-2 bg-blue-100 rounded text-xs text-blue-800">
                        <p className="font-medium mb-1">Posibles duplicados encontrados:</p>
                        {result.duplicates.map((dup, dupIdx) => (
                          <p key={dupIdx}>
                            • {dup.candidate_name} ({Math.round(dup.confidence * 100)}% coincidencia - {dup.match_type})
                          </p>
                        ))}
                      </div>
                    )}
                    
                    {/* Botones de acción */}
                    <div className="flex gap-2 mt-3">
                      {result.candidateId && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => navigate(`/candidates/${result.candidateId}`)}
                        >
                          Ver Perfil
                        </Button>
                      )}
                      {(result.status === 'failed' || result.status === 'partial_success') && result.candidateId && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => toast.info('Función de reintento próximamente')}
                        >
                          <RefreshCw className="w-3 h-3 mr-1" />
                          Reintentar
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              
              <div className="mt-6 flex gap-3">
                <Button
                  onClick={() => navigate('/candidates')}
                  className="flex-1"
                >
                  Ver Todos los Candidatos
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setUploadResults([])}
                >
                  Cargar Más
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Instructions */}
        <Card>
          <CardHeader>
            <CardTitle>Cómo Funciona Atlas IA</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="text-center">
                <div className="w-12 h-12 bg-cyan-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  <span className="text-xl font-bold text-cyan-600">1</span>
                </div>
                <h3 className="font-semibold text-slate-900 mb-2">Carga el CV</h3>
                <p className="text-sm text-slate-600">
                  Sube currículums en PDF o DOCX. Puedes cargar múltiples archivos a la vez.
                </p>
              </div>
              
              <div className="text-center">
                <div className="w-12 h-12 bg-cyan-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  <span className="text-xl font-bold text-cyan-600">2</span>
                </div>
                <h3 className="font-semibold text-slate-900 mb-2">Atlas Analiza</h3>
                <p className="text-sm text-slate-600">
                  La IA extrae datos estructurados y clasifica por industria, área funcional y seniority.
                </p>
              </div>
              
              <div className="text-center">
                <div className="w-12 h-12 bg-cyan-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  <span className="text-xl font-bold text-cyan-600">3</span>
                </div>
                <h3 className="font-semibold text-slate-900 mb-2">Revisa y Aprueba</h3>
                <p className="text-sm text-slate-600">
                  Revisa las clasificaciones de Atlas, edita si es necesario y aprueba el perfil.
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