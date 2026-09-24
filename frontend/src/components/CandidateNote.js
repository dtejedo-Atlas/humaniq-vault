import React, { useState } from 'react';
import { Pencil, Trash2, Check, X, Loader2 } from 'lucide-react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction } from './ui/alert-dialog';
import { useAuth } from '../contexts/AuthContext';
import { candidatesAPI } from '../api';

export const CandidateNote = ({ note, candidateId, onChanged, context = 'profile' }) => {
  const { user } = useAuth();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(note.note);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const admin = ['admin', 'super_admin'].includes(user?.role);
  const canMutate = Boolean(note.id && (admin || (note.created_by_id && note.created_by_id === user?.id)));
  const prefix = `note-${context}-${candidateId}-${note.id}`;
  const mutate = async remove => {
    setBusy(true); setError('');
    try {
      if (remove) await candidatesAPI.deleteNote(candidateId, note.id);
      else await candidatesAPI.editNote(candidateId, note.id, text.trim());
      setEditing(false); setConfirmDelete(false); await onChanged();
    } catch (e) { setError(e.response?.data?.detail || 'No se pudo guardar el cambio.'); }
    finally { setBusy(false); }
  };
  return (
    <div data-testid={prefix} className="min-w-0 space-y-2 rounded-sm bg-slate-50 p-3">
      {editing ? <Textarea data-testid={`${prefix}-edit-text`} aria-label="Texto de la nota" value={text} onChange={e => setText(e.target.value)} maxLength={10000} disabled={busy} /> : <p data-testid={`${prefix}-text`} className="whitespace-pre-wrap break-words text-sm text-slate-700">{note.note}</p>}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p data-testid={`${prefix}-author`} className="text-xs text-slate-500 break-words">{note.created_by} · {new Date(note.created_at).toLocaleString('es-MX')}{note.updated_at ? ' · Editada' : ''}</p>
        {canMutate && <div className="flex shrink-0 gap-1">
          {editing ? <><Button data-testid={`${prefix}-save`} aria-label="Guardar nota" title="Guardar nota" variant="ghost" size="icon" disabled={busy || !text.trim()} onClick={() => mutate(false)}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}</Button><Button data-testid={`${prefix}-cancel`} aria-label="Cancelar edición" title="Cancelar edición" variant="ghost" size="icon" disabled={busy} onClick={() => { setText(note.note); setEditing(false); }}><X className="h-4 w-4" /></Button></> : <><Button data-testid={`${prefix}-edit`} aria-label="Editar nota" title="Editar nota" variant="ghost" size="icon" onClick={() => setEditing(true)}><Pencil className="h-4 w-4" /></Button><Button data-testid={`${prefix}-delete`} aria-label="Eliminar nota" title="Eliminar nota" variant="ghost" size="icon" onClick={() => setConfirmDelete(true)}><Trash2 className="h-4 w-4 text-red-600" /></Button></>}
        </div>}
      </div>
      {!note.created_by_id && <p data-testid={`${prefix}-legacy-author`} className="text-xs text-slate-500">Autor histórico sin identificador verificable.</p>}
      {error && <p data-testid={`${prefix}-error`} role="alert" className="text-sm text-red-700">{typeof error === 'string' ? error : 'Texto de nota no válido.'}</p>}
      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}><AlertDialogContent data-testid={`${prefix}-delete-dialog`}><AlertDialogHeader><AlertDialogTitle>¿Eliminar esta nota?</AlertDialogTitle><AlertDialogDescription>La nota dejará de aparecer en la memoria compartida. Se conservará el registro de la eliminación.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel data-testid={`${prefix}-delete-cancel`} disabled={busy}>Cancelar</AlertDialogCancel><AlertDialogAction data-testid={`${prefix}-delete-confirm`} disabled={busy} onClick={e => { e.preventDefault(); mutate(true); }} className="bg-red-600 hover:bg-red-700">{busy ? 'Eliminando…' : 'Eliminar nota'}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    </div>
  );
};