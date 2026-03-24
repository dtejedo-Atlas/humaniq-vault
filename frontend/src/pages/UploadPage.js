import React, { useState, useCallback } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { candidatesAPI } from '../api';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

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
        results.push({
          fileName: file.name,
          success: true,
          candidateId: response.data.candidate_id,
          candidateName: response.data.parsed_data?.full_name || 'Desconocido'
        });
        toast.success(`CV procesado: ${file.name}`);
      } catch (error) {
        results.push({
          fileName: file.name,
          success: false,
          error: error.response?.data?.detail || 'Error desconocido'
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
                {uploadResults.filter(r => r.success).length} de {uploadResults.length} archivos procesados exitosamente
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {uploadResults.map((result, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between p-4 border border-slate-200 rounded-sm"
                  >
                    <div className="flex items-center gap-3 flex-1">
                      <FileText className="w-5 h-5 text-slate-400" />
                      <div className="flex-1">
                        <p className="text-sm font-medium text-slate-900">{result.fileName}</p>
                        {result.success && (
                          <p className="text-xs text-slate-600 mt-0.5">
                            Candidato: {result.candidateName}
                          </p>
                        )}
                        {!result.success && (
                          <p className="text-xs text-red-600 mt-0.5">
                            Error: {result.error}
                          </p>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-3">
                      {result.success ? (
                        <>
                          <CheckCircle className="w-5 h-5 text-green-500" />
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => navigate(`/candidates/${result.candidateId}`)}
                          >
                            Ver Perfil
                          </Button>
                        </>
                      ) : (
                        <AlertCircle className="w-5 h-5 text-red-500" />
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