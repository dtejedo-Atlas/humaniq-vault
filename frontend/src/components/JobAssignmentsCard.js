import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from './ui/select';
import { Loader2, ClipboardList } from 'lucide-react';
import { toast } from 'sonner';
import { jobsAPI, candidatesAPI } from '../api';
import { PlacedBadge, NotesBadge } from './CandidateBadges';

export const STAGE_LABELS = {
  new: 'Nuevo',
  reviewing: 'En revisión',
  qualified: 'Calificado',
  ready_to_send: 'Listo para enviar',
  submitted: 'Enviado a cliente',
  interviewed: 'Entrevistado',
  offer: 'Oferta',
  placed: 'Colocado',
  discarded: 'Descartado',
};

const JobAssignmentsCard = ({ jobId }) => {
  const [loading, setLoading] = useState(true);
  const [assignments, setAssignments] = useState([]);

  const load = useCallback(async () => {
    try {
      const res = await jobsAPI.getAssignments(jobId);
      setAssignments(res.data.assignments || []);
    } catch (error) {
      toast.error('Error al cargar candidatos asignados');
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleStageChange = async (candidateId, candidateName, stage) => {
    try {
      await candidatesAPI.updateAssignmentStage(candidateId, jobId, stage);
      if (stage === 'placed') {
        toast.success(`${candidateName} marcado como COLOCADO — restricción creada automáticamente`);
      } else {
        toast.success(`${candidateName} movido a "${STAGE_LABELS[stage]}"`);
      }
      load();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al actualizar etapa');
    }
  };

  return (
    <Card data-testid="job-assignments-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ClipboardList className="w-5 h-5" />
          Candidatos Asignados ({assignments.length})
        </CardTitle>
        <CardDescription>Pipeline de esta vacante — la etapa vive en el vínculo, no en el candidato</CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex justify-center py-6"><Loader2 className="w-5 h-5 animate-spin text-cyan-600" /></div>
        ) : assignments.length === 0 ? (
          <p className="text-sm text-slate-500 text-center py-4" data-testid="assignments-empty">
            Sin candidatos asignados. Usa "Asignar a vacante" desde los resultados de matching o el perfil del candidato.
          </p>
        ) : (
          <div className="space-y-2">
            {assignments.map((a) => (
              <div key={a.candidate_id} className="flex flex-col md:flex-row md:items-center gap-2 border rounded-lg p-3" data-testid="assignment-row">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Link to={`/candidates/${a.candidate_id}`} className="font-medium text-slate-900 hover:text-cyan-700 truncate">
                      {a.candidate_name}
                    </Link>
                    {a.is_placed && <PlacedBadge />}
                    <NotesBadge count={a.notes_count} />
                  </div>
                  <p className="text-xs text-slate-500 truncate">{a.current_title} · asignado por {a.assigned_by}</p>
                </div>
                <Select value={a.stage} onValueChange={(v) => handleStageChange(a.candidate_id, a.candidate_name, v)}>
                  <SelectTrigger className="md:w-48" data-testid="assignment-stage-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(STAGE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default JobAssignmentsCard;
