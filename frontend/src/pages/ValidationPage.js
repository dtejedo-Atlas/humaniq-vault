import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { CheckCircle, XCircle, AlertCircle, Download, TrendingUp } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';

const ValidationPage = () => {
  const [summary, setSummary] = useState(null);
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchValidationData();
  }, []);

  const fetchValidationData = async () => {
    try {
      const [summaryRes, recordsRes] = await Promise.all([
        axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/validation/summary`),
        axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/validation/records?limit=20`)
      ]);
      
      setSummary(summaryRes.data);
      setRecords(recordsRes.data);
    } catch (error) {
      console.error('Error fetching validation data:', error);
      toast.error('Error cargando datos de validación');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      const response = await axios.get(
        `${process.env.REACT_APP_BACKEND_URL}/api/validation/export`,
        { responseType: 'blob' }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'atlas_validation_records.csv');
      document.body.appendChild(link);
      link.click();
      link.remove();
      
      toast.success('Reporte exportado exitosamente');
    } catch (error) {
      console.error('Error exporting:', error);
      toast.error('Error exportando reporte');
    }
  };

  if (loading) {
    return (
      <Layout title="Validación de Calidad" subtitle="Tracking de precisión de Humaniq IA">
        <div className="flex items-center justify-center h-64">
          <div className="spinner w-8 h-8 border-4 border-slate-300 border-t-cyan-500 rounded-full"></div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title="Validación de Calidad" subtitle="Tracking de precisión de Humaniq IA">
      <div className="space-y-6">
        {/* Summary Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-slate-600">Total Evaluados</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-slate-900">{summary?.total_evaluated || 0}</div>
              <p className="text-xs text-slate-500 mt-1">Candidatos validados</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-slate-600">Precisión Industria</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-slate-900">{summary?.industry_accuracy || 0}%</div>
              <Progress value={summary?.industry_accuracy || 0} className="mt-2" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-slate-600">Precisión Área Funcional</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-slate-900">{summary?.functional_area_accuracy || 0}%</div>
              <Progress value={summary?.functional_area_accuracy || 0} className="mt-2" />
            </CardContent>
          </Card>
        </div>

        {/* Detailed Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Métricas de Calidad</CardTitle>
              <CardDescription>Precisión de clasificación de Humaniq IA</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Precisión Seniority</span>
                <span className="text-lg font-bold">{summary?.seniority_accuracy || 0}%</span>
              </div>
              <Progress value={summary?.seniority_accuracy || 0} />

              <div className="flex items-center justify-between pt-3">
                <span className="text-sm font-medium">Calidad de Parsing</span>
                <span className="text-lg font-bold">{summary?.avg_parsing_quality || 0}/5</span>
              </div>
              <Progress value={(summary?.avg_parsing_quality || 0) * 20} />

              <div className="flex items-center justify-between pt-3">
                <span className="text-sm font-medium">Relevancia de Búsqueda</span>
                <span className="text-lg font-bold">{summary?.search_relevance_rate || 0}%</span>
              </div>
              <Progress value={summary?.search_relevance_rate || 0} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Errores Comunes</CardTitle>
              <CardDescription>Clasificaciones incorrectas más frecuentes</CardDescription>
            </CardHeader>
            <CardContent>
              {summary?.common_errors && summary.common_errors.length > 0 ? (
                <div className="space-y-3">
                  {summary.common_errors.map((error, index) => (
                    <div key={index} className="flex items-start gap-3 p-3 bg-red-50 rounded-sm">
                      <AlertCircle className="w-5 h-5 text-red-500 mt-0.5" />
                      <div className="flex-1">
                        <p className="text-sm text-slate-700">{error.error}</p>
                        <p className="text-xs text-slate-500 mt-1">{error.count} ocurrencias</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-slate-500">
                  <CheckCircle className="w-12 h-12 mx-auto mb-2 text-green-500" />
                  <p>No hay errores registrados</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Recent Validations */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Validaciones Recientes</CardTitle>
              <CardDescription>Últimas 20 evaluaciones de calidad</CardDescription>
            </div>
            <Button variant="outline" onClick={handleExport} size="sm">
              <Download className="w-4 h-4 mr-2" />
              Exportar CSV
            </Button>
          </CardHeader>
          <CardContent>
            {records.length > 0 ? (
              <div className="space-y-3">
                {records.map((record) => (
                  <div key={record.id} className="p-4 border border-slate-200 rounded-sm">
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <h4 className="font-semibold text-slate-900">{record.candidate_name}</h4>
                        <p className="text-xs text-slate-500">
                          Evaluado por {record.reviewer_name} • {new Date(record.validated_at).toLocaleDateString('es-MX')}
                        </p>
                      </div>
                      {record.parsing_quality_score && (
                        <Badge variant="outline">
                          {record.parsing_quality_score}/5 parsing
                        </Badge>
                      )}
                    </div>

                    <div className="grid grid-cols-3 gap-3 mt-3">
                      <div>
                        <p className="text-xs text-slate-500 mb-1">Industria</p>
                        <div className="flex items-center gap-2">
                          {record.industry_correct === true ? (
                            <CheckCircle className="w-4 h-4 text-green-500" />
                          ) : record.industry_correct === false ? (
                            <XCircle className="w-4 h-4 text-red-500" />
                          ) : (
                            <div className="w-4 h-4" />
                          )}
                          <span className="text-sm">{record.atlas_industry || 'N/A'}</span>
                        </div>
                      </div>

                      <div>
                        <p className="text-xs text-slate-500 mb-1">Área Funcional</p>
                        <div className="flex items-center gap-2">
                          {record.functional_area_correct === true ? (
                            <CheckCircle className="w-4 h-4 text-green-500" />
                          ) : record.functional_area_correct === false ? (
                            <XCircle className="w-4 h-4 text-red-500" />
                          ) : (
                            <div className="w-4 h-4" />
                          )}
                          <span className="text-sm">{record.atlas_functional_area || 'N/A'}</span>
                        </div>
                      </div>

                      <div>
                        <p className="text-xs text-slate-500 mb-1">Seniority</p>
                        <div className="flex items-center gap-2">
                          {record.seniority_correct === true ? (
                            <CheckCircle className="w-4 h-4 text-green-500" />
                          ) : record.seniority_correct === false ? (
                            <XCircle className="w-4 h-4 text-red-500" />
                          ) : (
                            <div className="w-4 h-4" />
                          )}
                          <span className="text-sm">{record.atlas_seniority || 'N/A'}</span>
                        </div>
                      </div>
                    </div>

                    {record.comments && (
                      <p className="text-sm text-slate-600 mt-3 italic">"{record.comments}"</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-slate-500">
                <TrendingUp className="w-16 h-16 mx-auto mb-4 text-slate-300" />
                <p>No hay validaciones registradas aún</p>
                <p className="text-sm mt-2">Comienza evaluando candidatos desde sus perfiles</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

export default ValidationPage;
