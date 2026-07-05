import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Label } from './ui/label';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from './ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from './ui/select';
import { Loader2, UserPlus } from 'lucide-react';
import { toast } from 'sonner';
import { jobsAPI, candidatesAPI } from '../api';

const AssignJobDialog = ({ candidateId, candidateName, open, onOpenChange, onAssigned }) => {
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      jobsAPI.getAll()
        .then((res) => setJobs(res.data || []))
        .catch(() => toast.error('Error al cargar vacantes'));
    }
  }, [open]);

  const handleAssign = async () => {
    if (!selectedJob) {
      toast.error('Selecciona una vacante');
      return;
    }
    setSaving(true);
    try {
      await candidatesAPI.assignJob(candidateId, selectedJob);
      toast.success(`${candidateName} asignado a la vacante`);
      onOpenChange(false);
      setSelectedJob('');
      onAssigned?.();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al asignar candidato');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="assign-job-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserPlus className="w-5 h-5 text-cyan-600" />
            Asignar a vacante
          </DialogTitle>
          <DialogDescription>{candidateName} entrará a la vacante en etapa "Asignado"</DialogDescription>
        </DialogHeader>
        <div className="py-3 space-y-2">
          <Label>Vacante</Label>
          <Select value={selectedJob} onValueChange={setSelectedJob}>
            <SelectTrigger data-testid="assign-job-select">
              <SelectValue placeholder="Selecciona una vacante" />
            </SelectTrigger>
            <SelectContent>
              {jobs.map((j) => (
                <SelectItem key={j.id} value={j.id}>{j.title}{j.company ? ` — ${j.company}` : ''}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button onClick={handleAssign} disabled={saving} className="bg-cyan-600 hover:bg-cyan-700" data-testid="assign-job-confirm-btn">
            {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            Asignar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default AssignJobDialog;
