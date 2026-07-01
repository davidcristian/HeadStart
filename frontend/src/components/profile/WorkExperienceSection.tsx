/** Work experience rows for auto-apply profile editing. */

import { Button, Field } from "../ui";
import type { WorkExperienceEntry } from "../../types";
import { parseOptionalInt, updateRow } from "./profileFormUtils";

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

interface WorkExperienceSectionProps {
  workExperience: WorkExperienceEntry[];
  onWorkExperienceChange: (rows: WorkExperienceEntry[]) => void;
}

export function WorkExperienceSection({
  workExperience,
  onWorkExperienceChange,
}: WorkExperienceSectionProps) {
  return (
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
  );
}
