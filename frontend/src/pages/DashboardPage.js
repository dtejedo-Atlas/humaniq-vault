import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Users, UserPlus, Building2, Briefcase, TrendingUp, Clock, AlertTriangle, CheckCircle, AlertCircle } from 'lucide-react';
import { dashboardAPI, seedAPI } from '../api';
import { toast } from 'sonner';
import { formatRelativeTime } from '../utils/helpers';
import { useNavigate } from 'react-router-dom';

const DashboardPage = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      // Initialize seed data if needed
      try {
        await seedAPI.initializeData();
      } catch (e) {
        // Already initialized, ignore
        console.warn('Seed data initialization skipped:', e?.response?.status || e?.message);
      }

      const response = await dashboardAPI.getStats();
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching dashboard:', error);
      toast.error('Error cargando dashboard');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Layout title="Dashboard" subtitle="Visión general de tu base de talento">
        <div className="flex items-center justify-center h-64">
          <div className="spinner w-8 h-8 border-4 border-slate-300 border-t-cyan-500 rounded-full"></div>
        </div>
      </Layout>
    );
  }

  const statCards = [
    {
      title: 'Total Candidatos',
      value: stats?.total_candidates || 0,
      icon: Users,
      color: 'bg-blue-500',
      testId: 'total-candidates-stat'
    },
    {
      title: 'Nuevos Este Mes',
      value: stats?.new_this_month || 0,
      icon: UserPlus,
      color: 'bg-green-500',
      testId: 'new-candidates-stat'
    },
    {
      title: 'Vacantes Activas',
      value: stats?.job_metrics?.total_active_jobs || 0,
      icon: Briefcase,
      color: 'bg-purple-500',
      testId: 'active-jobs-stat'
    },
    {
      title: 'Industrias',
      value: Object.keys(stats?.by_industry || {}).length,
      icon: Building2,
      color: 'bg-orange-500',
      testId: 'industries-stat'
    }
  ];

  const jobMetrics = stats?.job_metrics;

  return (
    <Layout title="Dashboard" subtitle="Visión general de tu base de talento">
      <div className="space-y-6">
        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {statCards.map((stat) => {
            const Icon = stat.icon;
            return (
              <Card key={stat.title} data-testid={stat.testId} className="card-atlas">
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-slate-600">
                    {stat.title}
                  </CardTitle>
                  <div className={`${stat.color} w-10 h-10 rounded-sm flex items-center justify-center`}>
                    <Icon className="w-5 h-5 text-white" strokeWidth={1.5} />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-slate-900">{stat.value}</div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Job Metrics - Operational Focus */}
        {jobMetrics && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Jobs Without Candidates - ALERT */}
            <Card className={jobMetrics.jobs_without_candidates?.count > 0 ? 'border-red-300 bg-red-50' : ''}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    {jobMetrics.jobs_without_candidates?.count > 0 ? (
                      <AlertTriangle className="w-4 h-4 text-red-600" />
                    ) : (
                      <CheckCircle className="w-4 h-4 text-green-600" />
                    )}
                    Sin Candidatos
                  </CardTitle>
                  <span className={`text-2xl font-bold ${jobMetrics.jobs_without_candidates?.count > 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {jobMetrics.jobs_without_candidates?.count || 0}
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                {jobMetrics.jobs_without_candidates?.jobs?.length > 0 ? (
                  <div className="space-y-2">
                    {jobMetrics.jobs_without_candidates.jobs.slice(0, 3).map((job, i) => (
                      <div 
                        key={i} 
                        className="text-xs p-2 bg-white rounded cursor-pointer hover:bg-red-100 transition-colors"
                        onClick={() => navigate(`/jobs/${job.id}`)}
                      >
                        <div className="font-medium text-slate-800 truncate">{job.title}</div>
                        <div className="text-slate-500">{job.company}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-green-600">Todas las vacantes tienen candidatos</p>
                )}
              </CardContent>
            </Card>

            {/* Jobs Low Match - WARNING */}
            <Card className={jobMetrics.jobs_low_match?.count > 0 ? 'border-amber-300 bg-amber-50' : ''}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    {jobMetrics.jobs_low_match?.count > 0 ? (
                      <AlertCircle className="w-4 h-4 text-amber-600" />
                    ) : (
                      <CheckCircle className="w-4 h-4 text-green-600" />
                    )}
                    Bajo Match (&lt;3)
                  </CardTitle>
                  <span className={`text-2xl font-bold ${jobMetrics.jobs_low_match?.count > 0 ? 'text-amber-600' : 'text-green-600'}`}>
                    {jobMetrics.jobs_low_match?.count || 0}
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                {jobMetrics.jobs_low_match?.jobs?.length > 0 ? (
                  <div className="space-y-2">
                    {jobMetrics.jobs_low_match.jobs.slice(0, 3).map((job, i) => (
                      <div 
                        key={i} 
                        className="text-xs p-2 bg-white rounded cursor-pointer hover:bg-amber-100 transition-colors flex justify-between items-center"
                        onClick={() => navigate(`/jobs/${job.id}`)}
                      >
                        <div>
                          <div className="font-medium text-slate-800 truncate">{job.title}</div>
                          <div className="text-slate-500">{job.company}</div>
                        </div>
                        <span className="text-amber-700 font-semibold">{job.candidates}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-green-600">Todas las vacantes tienen buen match</p>
                )}
              </CardContent>
            </Card>

            {/* Top Jobs - SUCCESS */}
            <Card className="border-cyan-300 bg-cyan-50">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-cyan-600" />
                    Top Vacantes
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                {jobMetrics.top_jobs_with_candidates?.length > 0 ? (
                  <div className="space-y-2">
                    {jobMetrics.top_jobs_with_candidates.slice(0, 3).map((job, i) => (
                      <div 
                        key={i} 
                        className="text-xs p-2 bg-white rounded cursor-pointer hover:bg-cyan-100 transition-colors flex justify-between items-center"
                        onClick={() => navigate(`/jobs/${job.id}`)}
                      >
                        <div>
                          <div className="font-medium text-slate-800 truncate">{job.title}</div>
                          <div className="text-slate-500">{job.company}</div>
                        </div>
                        <span className="text-cyan-700 font-semibold bg-cyan-100 px-2 py-0.5 rounded">{job.candidates}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-500">No hay vacantes activas</p>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* By Industry */}
          <Card>
            <CardHeader>
              <CardTitle>Candidatos por Industria</CardTitle>
              <CardDescription>Top 5 industrias con más candidatos</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {Object.entries(stats?.by_industry || {}).slice(0, 5).map(([industry, count]) => (
                  <div key={industry} className="flex items-center justify-between">
                    <span className="text-sm text-slate-700">{industry}</span>
                    <div className="flex items-center gap-3">
                      <div className="w-32 h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-cyan-500"
                          style={{ width: `${(count / stats.total_candidates) * 100}%` }}
                        ></div>
                      </div>
                      <span className="text-sm font-semibold text-slate-900 w-8 text-right">{count}</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* By Functional Area */}
          <Card>
            <CardHeader>
              <CardTitle>Candidatos por Área Funcional</CardTitle>
              <CardDescription>Top 5 áreas funcionales</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {Object.entries(stats?.by_functional_area || {}).slice(0, 5).map(([area, count]) => (
                  <div key={area} className="flex items-center justify-between">
                    <span className="text-sm text-slate-700">{area}</span>
                    <div className="flex items-center gap-3">
                      <div className="w-32 h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-purple-500"
                          style={{ width: `${(count / stats.total_candidates) * 100}%` }}
                        ></div>
                      </div>
                      <span className="text-sm font-semibold text-slate-900 w-8 text-right">{count}</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Status Overview */}
        <Card>
          <CardHeader>
            <CardTitle>Estado de Candidatos</CardTitle>
            <CardDescription>Distribución por estado actual</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              {Object.entries(stats?.by_status || {}).map(([status, count]) => (
                <div key={status} className="text-center p-4 bg-slate-50 rounded-sm">
                  <div className="text-2xl font-bold text-slate-900">{count}</div>
                  <div className="text-xs text-slate-600 mt-1 capitalize">{status.replace('_', ' ')}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

export default DashboardPage;