import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Users, Briefcase, TrendingUp, Clock, AlertCircle, Lock, Loader2,
  Inbox, Activity, ChevronRight,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer,
  AreaChart, Area, PieChart, Pie, Cell, CartesianGrid,
} from 'recharts';
import { dashboardAPI } from '../api';
import { toast } from 'sonner';

const TURQUOISE = '#06B6D4';
const ORANGE = '#F97316';
const CALIBER_COLORS = { multinacional_global: '#06B6D4', corporativo_nacional: '#0E7490', mediana: '#155E75', pyme: '#F97316', startup: '#FDBA74' };
const CALIBER_LABELS = { multinacional_global: 'Multinacional', corporativo_nacional: 'Corporativo', mediana: 'Mediana', pyme: 'PyME', startup: 'Startup' };
const HEALTH_STYLES = {
  red: 'border-l-4 border-l-orange-500',
  yellow: 'border-l-4 border-l-amber-400',
  green: 'border-l-4 border-l-cyan-500',
};
const HEALTH_DOT = { red: 'bg-orange-500', yellow: 'bg-amber-400', green: 'bg-cyan-400' };
const STAGE_SHORT = { new: 'Asig', interviewed: 'Ent', placed: 'Col', discarded: 'Desc' };
const ACTION_LABELS = {
  candidate_created: 'creó al candidato',
  candidate_uploaded: 'subió el CV de',
  matching_run: 'corrió matching en',
  shortlist_exported: 'exportó shortlist de',
  note_added: 'comentó sobre',
  classification_approved: 'aprobó clasificación de',
  candidate_assigned: 'asignó a vacante a',
  candidate_placed: 'COLOCÓ a',
  assignment_stage_changed: 'movió de etapa a',
};

const timeAgo = (iso) => {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'hace un momento';
  if (diff < 3600) return `hace ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)} h`;
  return `hace ${Math.floor(diff / 86400)} d`;
};

const formatArea = (a) => (a || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const KpiCard = ({ icon: Icon, label, value, accent, testId }) => (
  <div data-testid={testId} className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col gap-1">
    <div className="flex items-center justify-between">
      <span className="text-[11px] uppercase tracking-wider text-slate-400">{label}</span>
      <Icon className={`w-4 h-4 ${accent || 'text-cyan-400'}`} />
    </div>
    <span className={`text-3xl font-bold ${accent || 'text-white'}`}>{value}</span>
  </div>
);

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    dashboardAPI.getOperational()
      .then((res) => setData(res.data))
      .catch((e) => {
        console.error('Dashboard error:', e);
        toast.error('Error al cargar el dashboard operativo');
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center bg-slate-950 rounded-2xl">
        <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
      </div>
    );
  }
  if (!data) {
    return <div className="p-8 text-center text-slate-500">No se pudo cargar el dashboard</div>;
  }

  const { kpis, jobs_board, recent_activity, action_inbox, charts } = data;
  const caliberData = charts.by_caliber.filter((c) => c.count > 0).map((c) => ({ ...c, name: CALIBER_LABELS[c.caliber] }));
  const areaData = charts.by_functional_area.map((a) => ({ ...a, name: formatArea(a.area) }));

  return (
    <div className="bg-slate-950 rounded-2xl p-4 md:p-6 space-y-5 -m-2" data-testid="operational-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Centro de Control</h1>
          <p className="text-sm text-slate-400">Operación del equipo en tiempo real</p>
        </div>
        <div className="hidden md:flex items-center gap-2 text-xs text-slate-500">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          Base universal · todas las vacantes visibles
        </div>
      </div>

      {/* ZONA 1: KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3" data-testid="kpi-row">
        <KpiCard icon={Users} label="Candidatos activos" value={kpis.total_candidates_active} testId="kpi-candidates" />
        <KpiCard icon={Briefcase} label="Vacantes activas" value={kpis.total_jobs_active} testId="kpi-jobs" />
        <KpiCard icon={TrendingUp} label="Nuevos este mes" value={kpis.candidates_this_month} testId="kpi-new-month" />
        <KpiCard icon={Clock} label="Días prom. abierta" value={kpis.avg_days_jobs_open} testId="kpi-days-open" />
        <KpiCard icon={AlertCircle} label="Por revisar" value={kpis.pending_classifications_count} accent={kpis.pending_classifications_count > 0 ? 'text-orange-400' : 'text-slate-500'} testId="kpi-pending" />
        <KpiCard icon={Lock} label="Colocados" value={kpis.placed_candidates_count} accent="text-cyan-400" testId="kpi-placed" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* ZONA 2: Tablero de vacantes */}
        <div className="lg:col-span-2 space-y-3" data-testid="jobs-board">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Tablero de Vacantes</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {jobs_board.map((job) => (
              <button
                key={job.id}
                onClick={() => navigate(`/jobs/${job.id}`)}
                className={`text-left bg-slate-900 border border-slate-800 rounded-xl p-4 hover:border-cyan-700 transition-colors ${HEALTH_STYLES[job.health]}`}
                data-testid="job-board-card"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold text-white truncate">{job.title}</p>
                    <p className="text-xs text-slate-400 truncate">{job.company || '—'} · {job.created_by}</p>
                  </div>
                  <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 mt-1 ${HEALTH_DOT[job.health]}`} data-testid={`job-health-${job.health}`} />
                </div>
                <div className="flex items-center gap-3 mt-3 text-xs text-slate-400">
                  <span>{job.days_open} días abierta</span>
                  <span>·</span>
                  <span>{job.assigned_total} asignados</span>
                </div>
                {job.assigned_total > 0 ? (
                  <div className="flex gap-1 mt-2 flex-wrap">
                    {Object.entries(job.candidates_by_stage).map(([stage, n]) => (
                      <span key={stage} className={`text-[10px] px-1.5 py-0.5 rounded ${stage === 'placed' ? 'bg-orange-500/20 text-orange-300' : 'bg-cyan-500/10 text-cyan-300'}`}>
                        {STAGE_SHORT[stage] || stage} {n}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-[10px] text-slate-600 mt-2">Sin pipeline aún</p>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* ZONA 3: Panel lateral */}
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4" data-testid="action-inbox">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
              <Inbox className="w-4 h-4 text-orange-400" /> Mi bandeja
            </h3>
            <div className="space-y-2 text-sm">
              <Link to="/review" className="flex items-center justify-between text-slate-300 hover:text-cyan-300 py-1" data-testid="inbox-pending-link">
                <span>Clasificaciones por revisar</span>
                <span className={`font-bold ${action_inbox.pending_classifications > 0 ? 'text-orange-400' : 'text-slate-500'}`}>{action_inbox.pending_classifications}</span>
              </Link>
              <Link to="/candidates" className="flex items-center justify-between text-slate-300 hover:text-cyan-300 py-1" data-testid="inbox-unassigned-link">
                <span>Mis candidatos sin vacante</span>
                <span className="font-bold text-slate-400">{action_inbox.my_unassigned_candidates}</span>
              </Link>
              {action_inbox.my_stale_jobs.length > 0 && (
                <div className="pt-1 border-t border-slate-800">
                  <p className="text-xs text-orange-400 mb-1">Mis vacantes sin actividad:</p>
                  {action_inbox.my_stale_jobs.map((j) => (
                    <Link key={j.id} to={`/jobs/${j.id}`} className="flex items-center text-xs text-slate-300 hover:text-cyan-300 py-0.5">
                      <ChevronRight className="w-3 h-3 mr-1" />{j.title}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4" data-testid="team-activity">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
              <Activity className="w-4 h-4 text-cyan-400" /> Actividad del equipo
            </h3>
            <div className="space-y-2.5 max-h-96 overflow-y-auto">
              {recent_activity.length === 0 && <p className="text-xs text-slate-500">Sin actividad registrada aún</p>}
              {recent_activity.map((ev) => (
                <div key={ev.id} className="flex gap-2 items-start" data-testid="activity-item">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-cyan-500/20 text-cyan-300 text-[10px] font-bold flex items-center justify-center mt-0.5">
                    {(ev.user_name || '?').charAt(0).toUpperCase()}
                  </span>
                  <div className="min-w-0 text-xs">
                    <p className="text-slate-300 leading-snug">
                      <span className="font-semibold text-white">{ev.user_name}</span>{' '}
                      {ACTION_LABELS[ev.action] || ev.action}{' '}
                      <Link
                        to={ev.entity_type === 'job' ? `/jobs/${ev.entity_id}` : `/candidates/${ev.entity_id}`}
                        className={`hover:underline ${ev.action === 'candidate_placed' ? 'text-orange-400 font-semibold' : 'text-cyan-300'}`}
                      >
                        {ev.entity_name || 'entidad'}
                      </Link>
                    </p>
                    <p className="text-slate-500">{timeAgo(ev.timestamp)}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ZONA 4: Gráficas */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4" data-testid="charts-row">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">Candidatos por área funcional</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={areaData} layout="vertical" margin={{ left: 10, right: 10 }}>
              <XAxis type="number" stroke="#475569" fontSize={10} />
              <YAxis type="category" dataKey="name" stroke="#94a3b8" fontSize={10} width={90} />
              <RTooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 12 }} labelStyle={{ color: '#e2e8f0' }} />
              <Bar dataKey="count" fill={TURQUOISE} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">Candidatos nuevos por semana</h3>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={charts.new_by_week} margin={{ left: -20, right: 10 }}>
              <defs>
                <linearGradient id="newGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={TURQUOISE} stopOpacity={0.5} />
                  <stop offset="100%" stopColor={TURQUOISE} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="week" stroke="#475569" fontSize={10} />
              <YAxis stroke="#475569" fontSize={10} allowDecimals={false} />
              <RTooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 12 }} labelStyle={{ color: '#e2e8f0' }} />
              <Area type="monotone" dataKey="count" stroke={TURQUOISE} fill="url(#newGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">Distribución por calibre de empresa</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={caliberData} dataKey="count" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
                {caliberData.map((entry) => (
                  <Cell key={entry.caliber} fill={CALIBER_COLORS[entry.caliber] || ORANGE} />
                ))}
              </Pie>
              <RTooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 12 }} labelStyle={{ color: '#e2e8f0' }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-2 justify-center mt-1">
            {caliberData.map((c) => (
              <span key={c.caliber} className="flex items-center gap-1 text-[10px] text-slate-400">
                <span className="w-2 h-2 rounded-full" style={{ background: CALIBER_COLORS[c.caliber] }} />
                {c.name} ({c.count})
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
