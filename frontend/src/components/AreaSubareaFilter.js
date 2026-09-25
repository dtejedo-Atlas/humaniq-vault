import React from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { useTaxonomy } from '../contexts/TaxonomyContext';

const ALL = ' ';

export const AreaSubareaFilter = ({ area = '', subarea = '', onChange, idPrefix = 'filter', renderOnly }) => {
  const { humaniqAreas } = useTaxonomy();
  const subareas = humaniqAreas.find((item) => item.key === area)?.subareas || [];
  const clean = (value) => (value && value.trim() ? value : '');

  return (
    <>
      {renderOnly !== 'subarea' && (
      <Select value={area} onValueChange={(value) => onChange(clean(value), '')}>
        <SelectTrigger data-testid={`${idPrefix}-presentation-area`}>
          <SelectValue placeholder="Área funcional" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Todas las áreas</SelectItem>
          {humaniqAreas.map((item) => (
            <SelectItem key={item.key} value={item.key}>{item.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>
      )}

      {renderOnly !== 'area' && (
      <Select value={subarea} disabled={!area} onValueChange={(value) => onChange(area, clean(value))}>
        <SelectTrigger data-testid={`${idPrefix}-presentation-subarea`}>
          <SelectValue placeholder={area ? 'Subárea' : 'Subárea (elige área)'} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Todas las subáreas</SelectItem>
          {subareas.map((sub) => (
            <SelectItem key={sub.key} value={sub.key}>{sub.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>
      )}
    </>
  );
};

export default AreaSubareaFilter;
