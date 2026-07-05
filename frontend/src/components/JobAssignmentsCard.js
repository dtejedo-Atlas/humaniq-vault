import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from './ui/select';
import { Loader2, ClipboardList, MessageSquare, ChevronDown, ChevronUp, Send } from 'lucide-react';
import { toast } from 'sonner';
import { jobsAPI, candidatesAPI } from '../api';
import { PlacedBadge } from './CandidateBadges';

export const STAGE_LABELS = {
  new: 'Asignado',
  interviewed: 'Entrevistado',
  placed: 'Colocado',
  discarded: 'Descartado',
};

const formatNoteDate = (iso) => {
  try {
    return new Date(iso).toLocaleDateString('es-MX', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return '';
  }
};

const AssignmentNotes = ({ candidateId, onNotesChanged }) => {
  const [loading, setLoading] = useState(true);
  const [notes, setNotes] = useState([]);
  const [newNote, setNewNote] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await candidatesAPI.getNotes(candidateId);
      setNotes(res.data.notes || []);
    } catch {
      toast.error('Error al cargar comentarios');
    } finally {
      setLoading(false);
    }
  }, [candidateId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAdd = async () => {
    if (!newNote.trim()) return;
    setSaving(true);
    try {
      await candidatesAPI.addNote(candidateId, newNote.trim());
      setNewNote('');
      await load();
      onNotesChanged?.();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al agregar comentario');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-2 bg-slate-50 border rounded-lg p-3 space-y-2" data-testid="assignment-notes-panel">
      {loading ? (
        <div className="flex justify-center py-2"><Loader2 className="w-4 h-4 animate-spin text-cyan-600" /></div>
      ) : notes.length === 0 ? (
        <p className="text-xs text-slate-500">Sin comentarios aún</p>
      ) : (
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {notes.slice().reverse().map((n, i) => (
            <div key={i} className="text-sm bg-white border rounded p-2" data-testid="assignment-note-item">
              <p className="text-slate-800 whitespace-pre-wrap">{n.note}</p>
              <p className="text-[11px] text-slate-400 mt-1">{n.created_by} · {formatNoteDate(n.created_at)}</p>
            </div>
          ))}
        </div>
      )}
      <div className="flex gap-2 items-end">
        <Textarea
          value={newNote}
          onChange={(e) => setNewNote(e.target.value)}
          placeholder="Agregar comentario..."
          rows={1}
          className="text-sm min-h-[38px]"
          data-testid="assignment-note-input"
        />
        <Button size="sm" onClick={handleAdd} disabled={saving || !newNote.trim()} className="bg-cyan-600 hover:bg-cyan-700 flex-shrink-0" data-testid="assignment-note-submit">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </Button>
      </div>
    </div>
  );
};

const JobAssignmentsCard = ({ jobId }) => {
  const [loading, setLoading] = useState(true);
  const [assignments, setAssignments] = useState([]);
  const [openNotes, setOpenNotes] = useState({});

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
        <CardDescription>Seguimiento simple: asignado, entrevistado, colocado o descartado — con comentarios del equipo</CardDescription>
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
              <div key={a.candidate_id} className="border rounded-lg p-3" data-testid="assignment-row">
                <div className="flex flex-col md:flex-row md:items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Link to={`/candidates/${a.candidate_id}`} className="font-medium text-slate-900 hover:text-cyan-700 truncate">
                        {a.candidate_name}
                      </Link>
                      {a.is_placed && <PlacedBadge />}
                    </div>
                    <p className="text-xs text-slate-500 truncate">{a.current_title} · asignado por {a.assigned_by}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setOpenNotes((p) => ({ ...p, [a.candidate_id]: !p[a.candidate_id] }))}
                    className="text-cyan-700 hover:text-cyan-800 justify-start md:justify-center"
                    data-testid="assignment-notes-toggle"
                  >
                    <MessageSquare className="w-4 h-4 mr-1" />
                    {a.notes_count || 0}
                    {openNotes[a.candidate_id] ? <ChevronUp className="w-3 h-3 ml-1" /> : <ChevronDown className="w-3 h-3 ml-1" />}
                  </Button>
                  <Select value={STAGE_LABELS[a.stage] ? a.stage : 'new'} onValueChange={(v) => handleStageChange(a.candidate_id, a.candidate_name, v)}>
                    <SelectTrigger className="md:w-44" data-testid="assignment-stage-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(STAGE_LABELS).map(([value, label]) => (
                        <SelectItem key={value} value={value}>{label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {openNotes[a.candidate_id] && (
                  <AssignmentNotes candidateId={a.candidate_id} onNotesChanged={load} />
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default JobAssignmentsCard;
