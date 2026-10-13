import type { Segment } from './types';

function formatVttTime(seconds: number): string {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);

  return `${hrs.toString().padStart(2, '0')}:${mins
    .toString()
    .padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(3, '0')}`;
}

export function segmentsToVtt(segments: Segment[]): string {
  let vtt = 'WEBVTT\n\n';
  for (const seg of segments) {
    vtt += `${seg.index}\n`;
    vtt += `${formatVttTime(seg.start)} --> ${formatVttTime(seg.end)}\n`;
    vtt += `${seg.text}\n\n`;
  }
  return vtt;
}

export function createVttBlobUrl(segments: Segment[]): string {
  const vttText = segmentsToVtt(segments);
  const blob = new Blob([vttText], { type: 'text/vtt;charset=utf-8' });
  return URL.createObjectURL(blob);
}
