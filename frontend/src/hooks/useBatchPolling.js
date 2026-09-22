import { useEffect, useRef } from 'react';
import { candidatesAPI } from '../api';

// Browser visibility changes only affect polling; the server owns processing.
export const useBatchPolling = (batchId, onStatus, onError) => {
  const callbacks = useRef({ onStatus, onError });
  callbacks.current = { onStatus, onError };
  useEffect(() => {
    if (!batchId) return;
    let disposed = false, inFlight = false, complete = false, timer;
    const poll = async () => {
      if (disposed || inFlight) return;
      clearTimeout(timer); inFlight = true;
      let delay = 1500;
      try {
        const { data } = await candidatesAPI.getBatchStatus(batchId);
        if (disposed) return;
        complete = data.is_complete;
        callbacks.current.onStatus(data);
      } catch (error) {
        if (disposed) return;
        callbacks.current.onError(error);
        delay = 5000;
        complete = [401, 403, 404].includes(error.response?.status);
      } finally {
        inFlight = false;
        if (!disposed && !complete && document.visibilityState !== 'hidden') timer = setTimeout(poll, delay);
      }
    };
    const resume = () => { if (document.visibilityState !== 'hidden') poll(); else clearTimeout(timer); };
    poll();
    document.addEventListener('visibilitychange', resume);
    window.addEventListener('focus', resume);
    window.addEventListener('online', resume);
    window.addEventListener('upload-batch-refresh', resume);
    return () => {
      disposed = true; clearTimeout(timer);
      document.removeEventListener('visibilitychange', resume);
      window.removeEventListener('focus', resume);
      window.removeEventListener('online', resume);
      window.removeEventListener('upload-batch-refresh', resume);
    };
  }, [batchId]);
};