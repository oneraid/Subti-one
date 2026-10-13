import { useEffect, useState, useCallback, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import type { Job } from '../lib/types';

export function useJob(jobId?: string) {
  const queryClient = useQueryClient();
  const [sseError, setSseError] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  // Fallback / initial polling query
  const query = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => (jobId ? api.getJob(jobId) : Promise.reject('No ID')),
    enabled: !!jobId,
    refetchInterval: (queryData) => {
      const currentJob = queryData.state.data;
      if (!currentJob) return false;

      // If hard sub burn-in is actively progressing on any language, poll every 1.2s
      const hasActiveBurn =
        currentJob.burn_progress &&
        Object.entries(currentJob.burn_progress).some(
          ([lang, prog]) => prog < 1.0 && !currentJob.burned_langs?.includes(lang)
        );
      if (hasActiveBurn) {
        return 1200;
      }

      // If SSE failed or job is still in progress, poll every 2.5s
      const status = currentJob.status;
      if (!status || status === 'done' || status === 'failed' || status === 'cancelled') {
        return false;
      }
      return sseError ? 2500 : 8000;
    },
  });

  const updateJobData = useCallback(
    (newJob: Job) => {
      queryClient.setQueryData(['job', jobId], newJob);
    },
    [jobId, queryClient]
  );

  useEffect(() => {
    if (!jobId) return;

    // If job is already terminal, don't open SSE
    const currentStatus = query.data?.status;
    if (currentStatus === 'done' || currentStatus === 'failed' || currentStatus === 'cancelled') {
      return;
    }

    const sseUrl = api.getEventsUrl(jobId);
    const es = new EventSource(sseUrl);
    esRef.current = es;

    es.addEventListener('progress', (e) => {
      try {
        const job: Job = JSON.parse(e.data);
        updateJobData(job);
      } catch (err) {
        console.error('SSE progress parse error:', err);
      }
    });

    es.addEventListener('done', (e) => {
      try {
        const job: Job = JSON.parse(e.data);
        updateJobData(job);
      } catch (err) {
        console.error('SSE done parse error:', err);
      }
      es.close();
    });

    es.addEventListener('error', (e) => {
      // SSE error or terminal error
      try {
        if ('data' in e && typeof (e as any).data === 'string') {
          const job: Job = JSON.parse((e as any).data);
          updateJobData(job);
        }
      } catch {
        // Ignored
      }
      setSseError(true);
      es.close();
    });

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [jobId, query.data?.status, updateJobData]);

  return {
    job: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}
