import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Button } from './ui/button';
import { Copy, Check, Mail, Phone, Linkedin, Eye, Download, UserRound } from 'lucide-react';
import { toast } from 'sonner';
import { CVViewerSheet, downloadCandidateCV } from './CVViewerSheet';
import { openCandidate } from '../utils/navigation';

const CopyChip = ({ icon: Icon, value, label, href, testId }) => {
  const [copied, setCopied] = useState(false);
  if (!value) return null;
  const copy = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      toast.success(`${label} copiado`);
      setTimeout(() => setCopied(false), 1500);
    } catch (_) {
      toast.error('No se pudo copiar');
    }
  };
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white pl-2 pr-1 py-0.5 text-xs text-slate-700 max-w-full" data-testid={testId}>
      <Icon className="w-3 h-3 text-slate-400 shrink-0" />
      {href ? (
        <a href={href} target="_blank" rel="noreferrer" className="truncate max-w-[180px] hover:underline" onClick={(e) => e.stopPropagation()}>{value}</a>
      ) : (
        <span className="truncate max-w-[180px]">{value}</span>
      )}
      <button type="button" onClick={copy} className="rounded-full p-0.5 hover:bg-slate-100" aria-label={`Copiar ${label}`} data-testid={`${testId}-copy`}>
        {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3 text-slate-500" />}
      </button>
    </span>
  );
};

export const CandidateQuickActions = ({ candidate, originLabel = 'vacante', compact = false, idPrefix = '' }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [viewerOpen, setViewerOpen] = useState(false);
  const id = candidate.candidate_id || candidate.id;
  const t = (name) => `${idPrefix}${name}-${id}`;
  const name = candidate.candidate_name || candidate.name || candidate.full_name;
  const hasCv = candidate.has_cv !== false;
  const linkedin = candidate.linkedin_url;
  const linkedinHref = linkedin && !/^https?:\/\//i.test(linkedin) ? `https://${linkedin}` : linkedin;

  const download = (e) => {
    e.stopPropagation();
    downloadCandidateCV(id).then(() => toast.success('CV descargado')).catch(() => toast.error('Error descargando CV'));
  };

  return (
    <div className="flex flex-wrap items-center gap-2" data-testid={t('quick-actions')} onClick={(e) => e.stopPropagation()}>
      <CopyChip icon={Mail} value={candidate.email} label="Email" href={candidate.email ? `mailto:${candidate.email}` : null} testId={t('contact-email')} />
      <CopyChip icon={Phone} value={candidate.phone} label="Teléfono" href={candidate.phone ? `tel:${candidate.phone}` : null} testId={t('contact-phone')} />
      <CopyChip icon={Linkedin} value={linkedin ? linkedin.replace(/^https?:\/\/(www\.)?/i, '') : null} label="LinkedIn" href={linkedinHref} testId={t('contact-linkedin')} />
      <span className="flex items-center gap-1 ml-auto">
        <Button variant="outline" size="sm" className="h-7 px-2 text-xs" disabled={!hasCv} onClick={(e) => { e.stopPropagation(); setViewerOpen(true); }} data-testid={t('view-cv')}>
          <Eye className="w-3.5 h-3.5 mr-1" /> Ver CV
        </Button>
        <Button variant="outline" size="sm" className="h-7 px-2 text-xs" disabled={!hasCv} onClick={download} data-testid={t('download-cv')}>
          <Download className="w-3.5 h-3.5 mr-1" /> {compact ? '' : 'Descargar CV'}
        </Button>
        <Button variant="ghost" size="sm" className="h-7 px-2 text-xs text-blue-700" onClick={(e) => { e.stopPropagation(); openCandidate(navigate, location, id, originLabel); }} data-testid={t('view-profile')}>
          <UserRound className="w-3.5 h-3.5 mr-1" /> Perfil
        </Button>
      </span>
      <CVViewerSheet candidateId={id} candidateName={name} open={viewerOpen} onOpenChange={setViewerOpen} />
    </div>
  );
};

export default CandidateQuickActions;
