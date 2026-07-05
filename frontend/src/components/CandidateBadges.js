import React from 'react';
import { Lock, MessageSquare } from 'lucide-react';
import { Badge } from './ui/badge';

export const isPlacedCandidate = (candidate) => {
  if (!candidate) return false;
  if (candidate.is_placed === true) return true;
  if (candidate.is_restricted && candidate.restriction_info?.category === 'placed_by_humaniq') return true;
  return (candidate.job_assignments || []).some((a) => a.stage === 'placed');
};

export const PlacedBadge = ({ className = '' }) => (
  <Badge data-testid="placed-badge" className={`bg-orange-500 hover:bg-orange-500 text-white border-0 font-bold tracking-wider text-[10px] ${className}`}>
    <Lock className="w-3 h-3 mr-1" />
    COLOCADO
  </Badge>
);

export const NotesBadge = ({ count, className = '' }) => {
  if (!count) return null;
  return (
    <span data-testid="notes-badge" className={`inline-flex items-center gap-1 text-xs text-cyan-700 bg-cyan-50 border border-cyan-200 rounded-full px-2 py-0.5 ${className}`}>
      <MessageSquare className="w-3 h-3" />
      {count}
    </span>
  );
};
