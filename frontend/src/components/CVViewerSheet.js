import React, { useEffect, useState } from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from './ui/sheet';
import { Button } from './ui/button';
import { Download, Loader2, FileWarning } from 'lucide-react';
import { candidatesAPI } from '../api';
import { toast } from 'sonner';

const authFetch = (url) =>
  fetch(url, { headers: { Authorization: `Bearer ${localStorage.getItem('atlas_token')}` } });

export const downloadCandidateCV = async (candidateId, fileName) => {
  const res = await authFetch(candidatesAPI.downloadCV(candidateId));
  if (!res.ok) throw new Error('No se pudo descargar el CV');
  const blob = await res.blob();
  const name = fileName || res.headers.get('content-disposition')?.match(/filename="?([^"]+)"?/)?.[1] || 'cv.pdf';
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
};

export const CVViewerSheet = ({ candidateId, candidateName, open, onOpenChange }) => {
  const [blobUrl, setBlobUrl] = useState(null);
  const [isPdf, setIsPdf] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open || !candidateId) return undefined;
    let revoke = null;
    setLoading(true);
    setError(null);
    authFetch(candidatesAPI.downloadCV(candidateId))
      .then(async (res) => {
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'CV no disponible');
        const type = res.headers.get('content-type') || '';
        const blob = await res.blob();
        setIsPdf(type.includes('pdf'));
        revoke = window.URL.createObjectURL(blob);
        setBlobUrl(revoke);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    return () => {
      if (revoke) window.URL.revokeObjectURL(revoke);
      setBlobUrl(null);
    };
  }, [open, candidateId]);

  const handleDownload = () =>
    downloadCandidateCV(candidateId).then(() => toast.success('CV descargado')).catch(() => toast.error('Error descargando CV'));

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-3xl p-0 flex flex-col" data-testid="cv-viewer-sheet">
        <SheetHeader className="px-5 pt-5 pb-3 border-b">
          <div className="flex items-start justify-between gap-3 pr-6">
            <div className="min-w-0">
              <SheetTitle className="truncate" data-testid="cv-viewer-title">CV · {candidateName}</SheetTitle>
              <SheetDescription>Vista previa sin salir de la vacante</SheetDescription>
            </div>
            <Button size="sm" variant="outline" onClick={handleDownload} data-testid="cv-viewer-download">
              <Download className="w-4 h-4 mr-1" /> Descargar
            </Button>
          </div>
        </SheetHeader>
        <div className="flex-1 min-h-0 bg-slate-100">
          {loading && (
            <div className="h-full flex items-center justify-center text-slate-500">
              <Loader2 className="w-6 h-6 animate-spin mr-2" /> Cargando CV…
            </div>
          )}
          {!loading && error && (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 gap-2 p-6 text-center" data-testid="cv-viewer-error">
              <FileWarning className="w-8 h-8 text-amber-500" />
              <p className="text-sm">{error}</p>
            </div>
          )}
          {!loading && !error && blobUrl && isPdf && (
            <iframe title={`CV ${candidateName}`} src={blobUrl} className="w-full h-full border-0" data-testid="cv-viewer-frame" />
          )}
          {!loading && !error && blobUrl && !isPdf && (
            <div className="h-full flex flex-col items-center justify-center gap-3 text-slate-600 p-6 text-center" data-testid="cv-viewer-docx">
              <FileWarning className="w-8 h-8 text-slate-400" />
              <p className="text-sm">Este CV es un archivo Word; el navegador no lo previsualiza. Descárgalo para abrirlo.</p>
              <Button onClick={handleDownload} data-testid="cv-viewer-docx-download">
                <Download className="w-4 h-4 mr-1" /> Descargar CV
              </Button>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
};

export default CVViewerSheet;
