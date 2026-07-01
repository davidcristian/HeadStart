/** Structured work experience and education rows for auto-apply. */

import { Button, Field } from "../ui";
import type { EducationEntry, WorkExperienceEntry } from "../../types";

export const EMPTY_WORK_EXPERIENCE: WorkExperienceEntry = {
  job_title: "",
  company: "",
  location: "",
  start_month: null,
  start_year: null,
  end_month: null,
  end_year: null,
  is_current: false,
  description: "",
};

export const EMPTY_EDUCATION: EducationEntry = {
  school: "",
  degree: "",
  field_of_study: "",
  start_year: null,
  end_year: null,
  gpa: "",
};

interface ExperienceEducationFormProps {
  workExperience: WorkExperienceEntry[];
  education: EducationEntry[];
  onWorkExperienceChange: (rows: WorkExperienceEntry[]) => void;
  onEducationChange: (rows: EducationEntry[]) => void;
}

function parseOptionalInt(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function updateRow<T>(rows: T[], index: number, patch: Partial<T>): T[] {
  return rows.map((row, i) => (i === index ? { ...row, ...patch } : row));
}

export function ExperienceEducationForm({
  workExperience,
  education,
  onWorkExperienceChange,
  onEducationChange,
}: ExperienceEducationFormProps) {
  return (
    <>
      <section className="profile-section">
        <div className="row-actions">
          <h2>Work experience</h2>
          <Button
            variant="ghost"
            onClick={() =>
              onWorkExperienceChange([...workExperience, { ...EMPTY_WORK_EXPERIENCE }])
            }
          >
            Add role
          </Button>
        </div>
        <p className="muted">
          Used by Workday auto-apply. Each row needs a title, company, and start month/year.
        </p>
        {workExperience.length === 0 && <p className="muted">No work experience saved yet.</p>}
        {workExperience.map((row, index) => (
          <div key={`work-${index}`} className="profile-repeat-card">
            <div className="row-actions">
              <strong>Role {index + 1}</strong>
              <Button
                variant="danger"
                onClick={() => onWorkExperienceChange(workExperience.filter((_, i) => i !== index))}
              >
                Remove
              </Button>
            </div>
            <div className="form-grid">
              <Field label="Job title">
                <input
                  value={row.job_title}
                  onChange={(e) =>
                    onWorkExperienceChange(
                      updateRow(workExperience, index, { job_title: e.target.value }),
                    )
                  }
                  placeholder="Software Engineer"
                />
              </Field>
              <Field label="Company">
                <input
                  value={row.company}
                  onChange={(e) =>
                    onWorkExperienceChange(
                      updateRow(workExperience, index, { company: e.target.value }),
                    )
                  }
                  placeholder="ACME Corp"
                />
              </Field>
              <Field label="Location">
                <input
                  value={row.location}
                  onChange={(e) =>
                    onWorkExperienceChange(
                      updateRow(workExperience, index, { location: e.target.value }),
                    )
                  }
                  placeholder="San Francisco, CA"
                />
              </Field>
            </div>
            <div className="form-grid">
              <Field label="Start month">
                <input
                  type="number"
                  min={1}
                  max={12}
                  value={row.start_month ?? ""}
                  onChange={(e) =>
                    onWorkExperienceChange(
                      updateRow(workExperience, index, {
                        start_month: parseOptionalInt(e.target.value),
                      }),
                    )
                  }
                />
              </Field>
              <Field label="Start year">
                <input
                  type="number"
                  min={1900}
                  max={2100}
                  value={row.start_year ?? ""}
                  onChange={(e) =>
                    onWorkExperienceChange(
                      updateRow(workExperience, index, {
                        start_year: parseOptionalInt(e.target.value),
                      }),
                    )
                  }
                />
              </Field>
              <Field label="Current role">
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={row.is_current}
                    onChange={(e) =>
                      onWorkExperienceChange(
                        updateRow(workExperience, index, {
                          is_current: e.target.checked,
                          end_month: e.target.checked ? null : row.end_month,
                          end_year: e.target.checked ? null : row.end_year,
                        }),
                      )
                    }
                  />
                  I currently work here
                </label>
              </Field>
            </div>
            {!row.is_current && (
              <div className="form-grid">
                <Field label="End month">
                  <input
                    type="number"
                    min={1}
                    max={12}
                    value={row.end_month ?? ""}
                    onChange={(e) =>
                      onWorkExperienceChange(
                        updateRow(workExperience, index, {
                          end_month: parseOptionalInt(e.target.value),
                        }),
                      )
                    }
                  />
                </Field>
                <Field label="End year">
                  <input
                    type="number"
                    min={1900}
                    max={2100}
                    value={row.end_year ?? ""}
                    onChange={(e) =>
                      onWorkExperienceChange(
                        updateRow(workExperience, index, {
                          end_year: parseOptionalInt(e.target.value),
                        }),
                      )
                    }
                  />
                </Field>
              </div>
            )}
            <Field label="Description">
              <textarea
                rows={4}
                value={row.description}
                onChange={(e) =>
                  onWorkExperienceChange(
                    updateRow(workExperience, index, { description: e.target.value }),
                  )
                }
                placeholder="Responsibilities and achievements"
              />
            </Field>
          </div>
        ))}
      </section>

      <section className="profile-section">
        <div className="row-actions">
          <h2>Education</h2>
          <Button
            variant="ghost"
            onClick={() => onEducationChange([...education, { ...EMPTY_EDUCATION }])}
          >
            Add school
          </Button>
        </div>
        <p className="muted">Used by Workday auto-apply. School name is required for each row.</p>
        {education.length === 0 && <p className="muted">No education saved yet.</p>}
        {education.map((row, index) => (
          <div key={`edu-${index}`} className="profile-repeat-card">
            <div className="row-actions">
              <strong>School {index + 1}</strong>
              <Button
                variant="danger"
                onClick={() => onEducationChange(education.filter((_, i) => i !== index))}
              >
                Remove
              </Button>
            </div>
            <div className="form-grid">
              <Field label="School">
                <input
                  value={row.school}
                  onChange={(e) =>
                    onEducationChange(updateRow(education, index, { school: e.target.value }))
                  }
                  placeholder="University of Example"
                />
              </Field>
              <Field label="Degree">
                <input
                  value={row.degree}
                  onChange={(e) =>
                    onEducationChange(updateRow(education, index, { degree: e.target.value }))
                  }
                  placeholder="Bachelor of Science"
                />
              </Field>
              <Field label="Field of study">
                <input
                  value={row.field_of_study}
                  onChange={(e) =>
                    onEducationChange(
                      updateRow(education, index, { field_of_study: e.target.value }),
                    )
                  }
                  placeholder="Computer Science"
                />
              </Field>
            </div>
            <div className="form-grid">
              <Field label="Start year">
                <input
                  type="number"
                  min={1900}
                  max={2100}
                  value={row.start_year ?? ""}
                  onChange={(e) =>
                    onEducationChange(
                      updateRow(education, index, { start_year: parseOptionalInt(e.target.value) }),
                    )
                  }
                />
              </Field>
              <Field label="End year">
                <input
                  type="number"
                  min={1900}
                  max={2100}
                  value={row.end_year ?? ""}
                  onChange={(e) =>
                    onEducationChange(
                      updateRow(education, index, { end_year: parseOptionalInt(e.target.value) }),
                    )
                  }
                />
              </Field>
              <Field label="GPA">
                <input
                  value={row.gpa}
                  onChange={(e) =>
                    onEducationChange(updateRow(education, index, { gpa: e.target.value }))
                  }
                  placeholder="3.8"
                />
              </Field>
            </div>
          </div>
        ))}
      </section>
    </>
  );
}
