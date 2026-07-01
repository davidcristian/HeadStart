import type { User } from "./auth";
import type { Job } from "./job";
import type { NotificationTarget } from "./target";
import type { Search } from "./search";
import type { Source } from "./source";
import type { CredentialExport } from "./credentials";

export interface ProfileLinks {
  linkedin: string;
  github: string;
  website: string;
}

export interface WorkExperienceEntry {
  job_title: string;
  company: string;
  location: string;
  start_month: number | null;
  start_year: number | null;
  end_month: number | null;
  end_year: number | null;
  is_current: boolean;
  description: string;
}

export interface EducationEntry {
  school: string;
  degree: string;
  field_of_study: string;
  start_year: number | null;
  end_year: number | null;
  gpa: string;
}

export interface LanguageEntry {
  language: string;
  proficiency: string;
  is_native: boolean;
}

export interface ProfileData {
  full_name: string;
  email: string;
  phone: string;
  location: string;
  links: ProfileLinks;
  resume_text: string;
  cover_letter_template: string;
  answers: Record<string, string>;
  work_experience: WorkExperienceEntry[];
  education: EducationEntry[];
  skills: string[];
  languages: LanguageEntry[];
}

export interface ResumeFileMeta {
  filename: string;
  content_type: string;
  size_bytes: number;
}

export interface Profile extends ProfileData {
  exists: boolean;
  updated_at: string | null;
  resume_file: ResumeFileMeta | null;
}

export interface UserDataExport {
  exported_at: string;
  format_version: number;
  account: User;
  sources: Source[];
  searches: Search[];
  targets: NotificationTarget[];
  credentials: CredentialExport[];
  profile: Profile | null;
  jobs: Job[];
}
