import React from 'react';
import { Link } from 'react-router-dom';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';

const CHIP_BASE = 'inline-flex items-center whitespace-nowrap align-middle';
const CHIP_STYLE = { fontFamily: "'Space Grotesk', sans-serif", fontSize: '11.5px', borderRadius: '4px', padding: '1px 6px', lineHeight: '16px', boxShadow: 'none' };
const CORAL = '#FF6B5B';
const AMBER = '#FFAA00';
const INK = '#272727';
const TEAL = '#0092AE';

const chipStyles = {
  rojo: { background: CORAL, color: INK, border: `1px solid ${CORAL}` },
  amarillo: { background: AMBER, color: INK, border: `1px solid ${AMBER}` },
  edad: { background: 'transparent', color: TEAL, border: `1px solid ${TEAL}` },
  duplicado: { background: 'transparent', color: INK, border: `1px solid ${INK}` },
};

const stabilityLabel = (s) => {
  const red = s.employers_5y > 3;
  const yellow = s.employers_5y === 3;
  if (s.level === 'rojo') return red ? `Inestable · ${s.employers_5y} en 5a` : `Inestable · ${s.employers_10y} en 10a`;
  return yellow ? `Revisar · ${s.employers_5y} en 5a` : `Revisar · ${s.employers_10y} en 10a`;
};

const ageLabel = (age) => {
  const mid = (age.rango_min + age.rango_max) / 2;
  return `≈${Math.floor(mid / 10) * 10}+ · est. ${age.rango_min}–${age.rango_max}`;
};

const StabilityTooltip = ({ stability }) => (
  <div className="space-y-1.5">
    <p className="font-medium">
      {stability.texto} · {stability.employers_5y} en 5 años · {stability.employers_10y} en 10 años
      {stability.fechas_aproximadas && ' · fechas aproximadas'}
    </p>
    <ul className="space-y-0.5">
      {(stability.timeline || []).slice(0, 8).map((t, i) => (
        <li key={i} className={t.cuenta ? '' : 'opacity-60'}>
          · {t.empleador}: {t.inicio} → {t.fin} ({t.meses} m){!t.cuenta && ' — no cuenta'}
        </li>
      ))}
    </ul>
    {(stability.estancias_cortas || []).length > 0 && (
      <p>Estancias cortas: {stability.estancias_cortas.map((s) => `${s.empleador} (${s.meses} m)`).join(', ')}</p>
    )}
    {(stability.huecos || []).length > 0 && (
      <p>Huecos: {stability.huecos.map((g) => `${g.desde} → ${g.hasta} (${g.meses} m)`).join(', ')}</p>
    )}
    {stability.sin_empleo_actual && <p>Sin empleo actual registrado</p>}
    <p className="opacity-70">Aviso informativo: no afecta puntuación, orden ni acción.</p>
  </div>
);

/** Avisos informativos: no cambian puntuación, orden ni acción, y no salen en el export al cliente. */
export const CandidateNotices = ({ stability, age, duplicate, candidateId }) => {
  const chips = [];

  if (duplicate) {
    chips.push({
      key: 'duplicado',
      label: 'Posible duplicado',
      style: chipStyles.duplicado,
      testId: `duplicate-badge-${candidateId}`,
      to: '/duplicates',
      tooltip: (
        <div className="space-y-1">
          <p className="font-medium">Posible duplicado de {duplicate.nombre || 'otra ficha'}</p>
          <p>{duplicate.motivo}</p>
          <p className="opacity-70">Solo aviso: no se fusiona nada automáticamente. Clic para revisar duplicados.</p>
        </div>
      ),
    });
  }
  if (stability && (stability.level === 'rojo' || stability.level === 'amarillo')) {
    chips.push({
      key: 'estabilidad',
      label: stabilityLabel(stability),
      style: chipStyles[stability.level],
      testId: `stability-badge-${candidateId}`,
      tooltip: <StabilityTooltip stability={stability} />,
    });
  }
  if (age?.notificacion && age?.edad_estimada != null) {
    chips.push({
      key: 'edad',
      label: ageLabel(age),
      style: chipStyles.edad,
      testId: `age-chip-${candidateId}`,
      tooltip: (
        <div className="space-y-1">
          <p className="font-medium">Edad estimada {age.rango_min}–{age.rango_max}</p>
          <p>Fuente: {age.fuente}{age.detalle ? ` · ${age.detalle}` : ''}</p>
          <p>Confianza: {age.confianza}{age['años_carrera'] != null ? ` · ${age['años_carrera']} años de carrera` : ''}</p>
          <p className="opacity-70">Estimación informativa: no afecta puntuación, orden ni acción.</p>
        </div>
      ),
    });
  }

  if (chips.length === 0) return null;

  const visible = chips.slice(0, 2);
  const hidden = chips.slice(2);

  return (
    <TooltipProvider delayDuration={120}>
      <span className="inline-flex items-center gap-1.5 align-middle" data-testid={`candidate-notices-${candidateId}`}>
        {visible.map((chip) => (
          <Tooltip key={chip.key}>
            <TooltipTrigger asChild>
              {chip.to ? (
                <Link
                  to={chip.to}
                  onClick={(e) => e.stopPropagation()}
                  className={CHIP_BASE}
                  style={{ ...CHIP_STYLE, ...chip.style }}
                  data-testid={chip.testId}
                >
                  {chip.label}
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); e.preventDefault(); }}
                  className={CHIP_BASE}
                  style={{ ...CHIP_STYLE, ...chip.style }}
                  data-testid={chip.testId}
                >
                  {chip.label}
                </button>
              )}
            </TooltipTrigger>
            <TooltipContent className="max-w-sm text-xs">{chip.tooltip}</TooltipContent>
          </Tooltip>
        ))}
        {hidden.length > 0 && (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); e.preventDefault(); }}
                className={CHIP_BASE}
                style={{ ...CHIP_STYLE, background: 'transparent', color: INK, border: `1px solid ${INK}` }}
                data-testid={`notices-more-${candidateId}`}
              >
                +{hidden.length}
              </button>
            </TooltipTrigger>
            <TooltipContent className="max-w-sm text-xs space-y-2">
              {hidden.map((chip) => (
                <div key={chip.key}>
                  <p className="font-medium">{chip.label}</p>
                  {chip.tooltip}
                </div>
              ))}
            </TooltipContent>
          </Tooltip>
        )}
      </span>
    </TooltipProvider>
  );
};

export const AgeEstimateLine = ({ age }) => {
  if (!age || age.edad_estimada == null) return null;
  return (
    <p className="text-sm text-slate-600" data-testid="age-estimate-line">
      <span className="font-medium text-slate-700">Edad estimada: </span>
      {age.rango_min}–{age.rango_max} (confianza {age.confianza} · {age.detalle})
    </p>
  );
};

export default CandidateNotices;
