import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { candidatesAPI } from '../api';
import { useAuth } from './AuthContext';
import { useBatchPolling } from '../hooks/useBatchPolling';
import { toast } from 'sonner';

const UploadBatchContext = createContext(null);
const keyFor = userId => `humaniq:upload-batch:${userId}`;
const readTracking = userId => {
  try { return JSON.parse(localStorage.getItem(keyFor(userId)) || '{}') || {}; }
  catch { return {}; }
};
const writeTracking = (userId, value) => {
  try { localStorage.setItem(keyFor(userId), JSON.stringify(value)); }
  catch { /* The server's latest-batch lookup remains the fallback. */ }
};
const EMPTY = { batchId: null, status: null, transferring: false, recovering: true, error: '', unavailable: false };

export const UploadBatchProvider = ({ children }) => {
  const { user } = useAuth();
  const owner = user?.id;
  const ownerRef = useRef(owner); ownerRef.current = owner;
  const generation = useRef(0);
  const submitting = useRef(false);
  const [state, setState] = useState({ ...EMPTY, owner: null });
  const current = state.owner === owner ? state : EMPTY;

  useEffect(() => {
    generation.current += 1;
    submitting.current = false;
    if (!owner) { setState({ ...EMPTY, owner: null, recovering: false }); return; }
    const cached = readTracking(owner);
    setState({ ...EMPTY, owner, batchId: cached.batch_id || null });
    const recover = async () => {
      if (submitting.current) return;
      const request = generation.current;
      try {
        const { data } = await candidatesAPI.getLatestBatch();
        if (generation.current !== request || ownerRef.current !== owner) return;
        const tracking = readTracking(owner);
        const id = data.batch_id && data.batch_id !== tracking.dismissed_batch_id ? data.batch_id : null;
        setState(prev => ({ ...prev, batchId: id, status: prev.batchId === id ? prev.status : null, recovering: false, error: '' }));
        writeTracking(owner, { ...tracking, batch_id: id });
      } catch {
        if (generation.current === request) setState(prev => ({ ...prev, recovering: false, error: 'No se pudo recuperar el último lote. Se volverá a intentar al recuperar la conexión.' }));
      }
    };
    const recoverIfNeeded = () => { if (!readTracking(owner).batch_id) recover(); };
    recover();
    window.addEventListener('online', recoverIfNeeded);
    window.addEventListener('focus', recoverIfNeeded);
    window.addEventListener('upload-batch-refresh', recoverIfNeeded);
    return () => { generation.current += 1; window.removeEventListener('online', recoverIfNeeded); window.removeEventListener('focus', recoverIfNeeded); window.removeEventListener('upload-batch-refresh', recoverIfNeeded); };
  }, [owner]);

  const receive = useCallback(data => {
    setState(prev => prev.owner !== ownerRef.current || prev.batchId !== data.batch_id ? prev : { ...prev, status: data, recovering: false, error: '', unavailable: false });
  }, []);
  const pollingError = useCallback(error => {
    const unavailable = [403, 404].includes(error.response?.status);
    setState(prev => ({ ...prev, recovering: false, unavailable, error: unavailable ? 'Este lote no está disponible. Puedes cerrar este seguimiento.' : 'Conexión interrumpida. El servidor sigue procesando; el progreso se actualizará al reconectar.' }));
  }, []);
  useBatchPolling(owner ? current.batchId : null, receive, pollingError);

  const uploadBatch = useCallback(async files => {
    if (!owner || submitting.current) return;
    submitting.current = true; generation.current += 1;
    setState({ ...EMPTY, owner, transferring: true, recovering: false });
    try {
      const { data } = await candidatesAPI.uploadBatch(files);
      writeTracking(owner, { batch_id: data.batch_id });
      if (ownerRef.current === owner) {
        setState({ ...EMPTY, owner, batchId: data.batch_id, recovering: false });
        toast.info(`${data.queued} archivos recibidos para procesamiento`);
        if (data.rejected) toast.warning(`${data.rejected} archivos rechazados`);
      }
      return data;
    } catch (error) {
      if (ownerRef.current === owner) {
        setState(prev => ({ ...prev, transferring: false, error: 'No se pudo confirmar la recepción. Actualiza el seguimiento antes de volver a enviar archivos.' }));
        toast.error('No se pudo confirmar la carga de lote');
        // A lost response does not mean the server did not receive the upload.
        try {
          const { data } = await candidatesAPI.getLatestBatch();
          if (ownerRef.current === owner && data.batch_id) {
            writeTracking(owner, { batch_id: data.batch_id });
            setState(prev => ({ ...prev, batchId: data.batch_id }));
          }
        } catch { /* Keep the connection error visible; do not submit again automatically. */ }
      }
    } finally { if (ownerRef.current === owner) submitting.current = false; }
  }, [owner]);

  const resetBatch = useCallback(() => {
    writeTracking(owner, { dismissed_batch_id: current.batchId });
    setState({ ...EMPTY, owner, recovering: false });
  }, [owner, current.batchId]);
  const refreshBatch = useCallback(() => window.dispatchEvent(new Event('upload-batch-refresh')), []);
  const value = {
    currentBatchId: current.batchId, batchStatus: current.status,
    uploading: current.transferring || current.recovering || Boolean(current.batchId && !current.status?.is_complete && !current.unavailable),
    transferring: current.transferring, recovering: current.recovering, syncError: current.error,
    unavailable: current.unavailable, uploadBatch, resetBatch, refreshBatch,
  };
  return <UploadBatchContext.Provider value={value}>{children}</UploadBatchContext.Provider>;
};

export const useUploadBatch = () => useContext(UploadBatchContext);