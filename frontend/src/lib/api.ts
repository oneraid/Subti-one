import type { ConfigResponse, HealthResponse, Job, Segment, SubtitleResponse } from './types';

export class ApiRequestError extends Error {
  code: string;
  status: number;

  constructor(message: string, code = 'unknown_error', status = 500) {
    super(message);
    this.name = 'ApiRequestError';
    this.code = code;
    this.status = status;
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(endpoint, options);
  if (!res.ok) {
    let errorMsg = `Request gagal dengan status ${res.status}`;
    let errorCode = 'http_error';
    try {
      const data = await res.json();
      if (data.error) {
        errorMsg = data.error.message || errorMsg;
        errorCode = data.error.code || errorCode;
      }
    } catch {
      // Body not JSON
    }
    throw new ApiRequestError(errorMsg, errorCode, res.status);
  }

  if (res.status === 204) {
    return null as T;
  }

  return res.json() as Promise<T>;
}

export const api = {
  getConfig: () => request<ConfigResponse>('/api/config'),
  getHealth: () => request<HealthResponse>('/api/health'),
  getJobs: () => request<Job[]>('/api/jobs'),
  getJob: (id: string) => request<Job>(`/api/jobs/${id}`),

  createJob: (formData: FormData) =>
    request<Job>('/api/jobs', {
      method: 'POST',
      body: formData,
    }),

  cancelJob: (id: string) =>
    request<Job>(`/api/jobs/${id}/cancel`, {
      method: 'POST',
    }),

  deleteJob: (id: string) =>
    request<void>(`/api/jobs/${id}`, {
      method: 'DELETE',
    }),

  getSubtitles: (id: string, lang: string) =>
    request<SubtitleResponse>(`/api/jobs/${id}/subtitles/${lang}`),

  updateSubtitles: (id: string, lang: string, segments: Segment[]) =>
    request<SubtitleResponse>(`/api/jobs/${id}/subtitles/${lang}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ segments }),
    }),

  translateJob: (id: string, targetLangs: string[]) =>
    request<Job>(`/api/jobs/${id}/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_langs: targetLangs }),
    }),

  burnJob: (id: string, lang: string, mode: 'hard' | 'soft' = 'hard') =>
    request<Job>(`/api/jobs/${id}/burn`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lang, mode }),
    }),

  getDownloadUrl: (
    id: string,
    lang: string,
    format: 'srt' | 'vtt' = 'srt',
    bilingual = false,
    order: 'source_first' | 'target_first' = 'source_first'
  ) => {
    const params = new URLSearchParams({
      format,
      bilingual: String(bilingual),
      order,
    });
    return `/api/jobs/${id}/subtitles/${lang}/download?${params.toString()}`;
  },

  getMediaUrl: (id: string) => `/api/jobs/${id}/media`,
  getBurnedUrl: (id: string, lang: string) => `/api/jobs/${id}/burned/${lang}`,
  getSoftsubUrl: (id: string, lang: string) => `/api/jobs/${id}/softsub/${lang}`,
  getEventsUrl: (id: string) => `/api/jobs/${id}/events`,
};
