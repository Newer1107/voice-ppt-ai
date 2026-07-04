export interface LectureSummary {
  id: string;
  title: string;
  input_type: string;
  status: string;
  duration_seconds?: number;
  created_at: string;
}

export interface LectureDetail {
  id: string;
  project_id: string;
  title: string;
  input_type: string;
  status: string;
  duration_seconds?: number;
  slides: SlideNarration[];
  transcript_url?: string;
  narrated_pptx_url?: string;
  created_at: string;
  updated_at: string;
}

export interface SlideNarration {
  id: string;
  slide_number: number;
  raw_text?: string;
  narration?: NarrationSummary;
}

export interface NarrationSummary {
  id: string;
  script_text: string;
  audio_url?: string;
  duration_seconds?: number;
  status: string;
}

export interface LectureStatus {
  id: string;
  status: string;
  progress: number;
  current_stage?: string;
  jobs: JobSummary[];
  error_message?: string;
}

export interface JobSummary {
  id: string;
  job_type: string;
  status: string;
  progress: number;
}

export interface VoiceProfile {
  id: string;
  name: string;
  status: string;
  created_at: string;
}
