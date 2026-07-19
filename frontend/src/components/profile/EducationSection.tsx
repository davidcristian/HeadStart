/** Education rows for auto-apply profile editing. */

import { Button, Field } from "../ui";
import type { EducationEntry } from "../../types";
import { parseOptionalInt, updateRow } from "./profileFormUtils";

export const EMPTY_EDUCATION: EducationEntry = {
  school: "",
  degree: "",
  field_of_study: "",
  start_year: null,
  end_year: null,
  gpa: "",
};

interface EducationSectionProps {
  education: EducationEntry[];
  onEducationChange: (rows: EducationEntry[]) => void;
}

export function EducationSection({ education, onEducationChange }: EducationSectionProps) {
  return (
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
                  onEducationChange(updateRow(education, index, { field_of_study: e.target.value }))
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
                    updateRow(education, index, {
                      start_year: parseOptionalInt(e.target.value, 1900, 2100),
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
                  onEducationChange(
                    updateRow(education, index, {
                      end_year: parseOptionalInt(e.target.value, 1900, 2100),
                    }),
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
  );
}
