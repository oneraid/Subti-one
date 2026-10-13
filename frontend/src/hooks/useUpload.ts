import { useState } from 'react';
import type { Job } from '../lib/types';

interface UploadOptions {
  sourceLang: string;
  targetLangs: string[];
  modelSize: string;
  glossary?: Record<string, string>;
  onSuccess?: (job: Job) => void;
  onError?: (err: Error) => void;
}

export function useUpload() {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0); // 0 - 100
  const [error, setError] = useState<string | null>(null);

  const uploadFile = (file: File, options: UploadOptions) => {
    setIsUploading(true);
    setUploadProgress(0);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_lang', options.sourceLang);
    if (options.targetLangs.length > 0) {
      formData.append('target_langs', options.targetLangs.join(','));
    }
    formData.append('model_size', options.modelSize);
    if (options.glossary && Object.keys(options.glossary).length > 0) {
      formData.append('glossary', JSON.stringify(options.glossary));
    }

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/jobs');

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        const percent = Math.round((event.loaded / event.total) * 100);
        setUploadProgress(percent);
      }
    };

    xhr.onload = () => {
      setIsUploading(false);
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const job: Job = JSON.parse(xhr.responseText);
          options.onSuccess?.(job);
        } catch {
          const err = new Error('Gagal membaca respon server');
          setError(err.message);
          options.onError?.(err);
        }
      } else {
        let msg = `Gagal mengunggah file (${xhr.status})`;
        try {
          const data = JSON.parse(xhr.responseText);
          if (data.error?.message) {
            msg = data.error.message;
          }
        } catch {
          // Fallback message
        }
        const err = new Error(msg);
        setError(msg);
        options.onError?.(err);
      }
    };

    xhr.onerror = () => {
      setIsUploading(false);
      const err = new Error('Terjadi kesalahan jaringan saat mengunggah');
      setError(err.message);
      options.onError?.(err);
    };

    xhr.send(formData);
  };

  return {
    uploadFile,
    isUploading,
    uploadProgress,
    error,
    clearError: () => setError(null),
  };
}
