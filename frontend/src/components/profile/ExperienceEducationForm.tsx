/** Structured work experience and education rows for auto-apply. */

import type { EducationEntry, WorkExperienceEntry } from "../../types";
import { EducationSection } from "./EducationSection";
import { WorkExperienceSection } from "./WorkExperienceSection";

export { EMPTY_EDUCATION } from "./EducationSection";
export { EMPTY_WORK_EXPERIENCE } from "./WorkExperienceSection";

interface ExperienceEducationFormProps {
  workExperience: WorkExperienceEntry[];
  education: EducationEntry[];
  onWorkExperienceChange: (rows: WorkExperienceEntry[]) => void;
  onEducationChange: (rows: EducationEntry[]) => void;
}

export function ExperienceEducationForm({
  workExperience,
  education,
  onWorkExperienceChange,
  onEducationChange,
}: ExperienceEducationFormProps) {
  return (
    <>
      <WorkExperienceSection
        workExperience={workExperience}
        onWorkExperienceChange={onWorkExperienceChange}
      />
      <EducationSection education={education} onEducationChange={onEducationChange} />
    </>
  );
}
