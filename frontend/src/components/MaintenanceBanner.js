import React, { useEffect, useState } from 'react';
import { Wrench } from 'lucide-react';
import { systemAPI } from '../api';

export const MaintenanceBanner = () => {
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const { data } = await systemAPI.getMaintenanceNotice();
        if (alive) setNotice(data?.active ? data : null);
      } catch {
        if (alive) setNotice(null);
      }
    };
    load();
    const timer = setInterval(load, 120000);
    return () => { alive = false; clearInterval(timer); };
  }, []);

  if (!notice) return null;

  const cuando = notice.scheduled_at
    ? new Date(notice.scheduled_at).toLocaleString('es-MX', {
        day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit',
      }).replace(/\.$/, '')
    : null;

  return (
    <div
      data-testid="maintenance-banner"
      className="flex items-start gap-3 border-b border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 sm:px-6"
    >
      <Wrench className="mt-0.5 h-4 w-4 shrink-0" />
      <p>
        <span className="font-semibold">Mantenimiento programado{cuando ? ` · ${cuando}` : ''}.</span>{' '}
        {notice.message || 'Evita subir CVs durante la actualización: una carga a medias se interrumpe y hay que reintentarla.'}
      </p>
    </div>
  );
};

export default MaintenanceBanner;
