import React from 'react';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

export const ReviewField = ({ candidateId, field, label, value, options, disabled, onChange }) => {
  const id = `review-${field}-${candidateId}`;
  const known = value == null || options.some(option => String(option.key) === String(value));
  return (
    <div className="min-w-0 space-y-2">
      <Label htmlFor={id} className="text-xs font-semibold text-slate-700">{label}</Label>
      <Select value={value == null ? '__unset__' : String(value)} onValueChange={v => onChange(field, v === '__unset__' ? null : field === 'years_experience' ? Number(v) : v)} disabled={disabled}>
        <SelectTrigger id={id} data-testid={id} className={`w-full bg-white ${known ? '' : 'border-amber-500'}`}>
          <SelectValue placeholder="Sin dato" />
        </SelectTrigger>
        <SelectContent data-testid={`${id}-options`} className="max-w-[calc(100vw-2rem)]">
          <SelectItem data-testid={`${id}-unset`} value="__unset__">Sin dato</SelectItem>
          {!known && <SelectItem data-testid={`${id}-invalid`} value={String(value)} disabled>{value} · Fuera de catálogo</SelectItem>}
          {options.map(option => <SelectItem data-testid={`${id}-option-${option.key}`} key={option.key} value={String(option.key)}>{option.name_es || option.label || option.key}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  );
};