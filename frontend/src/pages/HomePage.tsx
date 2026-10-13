import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import UploadForm from '../components/UploadForm';
import JobList from '../components/JobList';
import type { Job } from '../lib/types';

export default function HomePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: api.getConfig,
  });

  const { data: jobs = [], isLoading: jobsLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: api.getJobs,
    refetchInterval: 5000,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteJob(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => api.cancelJob(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  const handleJobCreated = (job: Job) => {
    queryClient.invalidateQueries({ queryKey: ['jobs'] });
    navigate(`/jobs/${job.id}`);
  };

  return (
    <div className="space-y-10 animate-fade-in">
      {/* Hero section */}
      <div className="text-center max-w-2xl mx-auto space-y-3">
        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-indigo-200 to-purple-400">
          Auto Subtitle & AI Translator
        </h1>
        <p className="text-sm sm:text-base text-slate-400 leading-relaxed">
          Transkripsi akurat berbasis Faster-Whisper dan terjemahan subtitle lisan alami
          menggunakan Claude AI untuk video dan audio Anda.
        </p>
      </div>

      {/* Upload Form */}
      <div className="max-w-4xl mx-auto">
        <UploadForm config={config} onJobCreated={handleJobCreated} />
      </div>

      {/* Job List */}
      <div className="max-w-4xl mx-auto">
        <JobList
          jobs={jobs}
          isLoading={jobsLoading}
          onDeleteJob={(id) => {
            if (confirm('Yakin ingin menghapus pekerjaan ini beserta seluruh filenya?')) {
              deleteMutation.mutate(id);
            }
          }}
          onCancelJob={(id) => cancelMutation.mutate(id)}
        />
      </div>
    </div>
  );
}
