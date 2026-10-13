export type SourceLangCode = 'auto' | 'id' | 'en' | 'zh';
export type TargetLangCode = 'en' | 'id';

export interface Segment {
  index: number;
  start: number;
  end: number;
  text: string;
}

export type JobStatus =
  | 'queued'
  | 'extracting_audio'
  | 'transcribing'
  | 'segmenting'
  | 'translating'
  | 'done'
  | 'failed'
  | 'cancelled';

export interface Job {
  id: string;
  filename: string;
  status: JobStatus;
  stage_progress: number;
  progress: number;
  source_lang_requested: SourceLangCode;
  source_lang_detected?: string | null;
  target_langs: TargetLangCode[];
  model_size: string;
  duration_sec?: number | null;
  available_langs: string[];
  burned_langs?: string[];
  softsub_langs?: string[];
  burn_progress?: Record<string, number>;
  warnings?: string[];
  error?: string | null;
  created_at: string;
}

export interface LanguageOption {
  code: string;
  label: string;
}

export interface ConfigResponse {
  source_languages: LanguageOption[];
  target_languages: LanguageOption[];
  whisper_models: string[];
  default_model: string;
  max_upload_mb: number;
}

export interface HealthResponse {
  status: string;
  ffmpeg: boolean;
  whisper_model: string;
  translator: string;
  translator_ready: boolean;
}

export interface SubtitleResponse {
  lang: string;
  segments: Segment[];
}

export interface ApiError {
  error: {
    code: string;
    message: string;
  };
}
