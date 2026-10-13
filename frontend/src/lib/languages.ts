import type { LanguageOption } from './types';

export const SOURCE_LANGUAGES: LanguageOption[] = [
  { code: 'auto', label: 'Otomatis' },
  { code: 'id', label: 'Indonesia' },
  { code: 'en', label: 'English' },
  { code: 'zh', label: '中文' },
];

export const TARGET_LANGUAGES: LanguageOption[] = [
  { code: 'en', label: 'English' },
  { code: 'id', label: 'Indonesia' },
];

export const LANGUAGE_NAMES: Record<string, string> = {
  auto: 'Otomatis',
  id: 'Indonesia',
  en: 'Inggris',
  zh: 'Mandarin',
};

export const WHISPER_MODELS: string[] = ['tiny', 'base', 'small', 'medium', 'large-v3'];
export const DEFAULT_WHISPER_MODEL = 'small';

export function getLanguageName(code: string): string {
  return LANGUAGE_NAMES[code] || code.toUpperCase();
}
