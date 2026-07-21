/** Structured skills and languages for Workday auto-apply. */

import { Button, Field } from "../ui";
import type { LanguageEntry } from "../../types";
import { updateRow } from "./profileFormUtils";

export const EMPTY_LANGUAGE: LanguageEntry = {
  language: "",
  proficiency: "",
  is_native: false,
};

interface SkillsLanguagesFormProps {
  skills: string[];
  languages: LanguageEntry[];
  onSkillsChange: (skills: string[]) => void;
  onLanguagesChange: (rows: LanguageEntry[]) => void;
}

export function SkillsLanguagesForm({
  skills,
  languages,
  onSkillsChange,
  onLanguagesChange,
}: SkillsLanguagesFormProps) {
  return (
    <>
      <section className="profile-section">
        <div className="row-actions">
          <h2>Skills</h2>
          <Button variant="ghost" onClick={() => onSkillsChange([...skills, ""])}>
            Add skill
          </Button>
        </div>
        <p className="muted">
          Used by Workday auto-apply. Match job-posting terminology when possible; some tenants
          require exact skill names from their catalog.
        </p>
        {skills.length === 0 && <p className="muted">No skills saved yet.</p>}
        {skills.map((skill, index) => (
          <div key={`skill-${index}`} className="profile-repeat-card">
            <div className="row-actions">
              <strong>Skill {index + 1}</strong>
              <Button
                variant="danger"
                onClick={() => onSkillsChange(skills.filter((_, i) => i !== index))}
              >
                Remove
              </Button>
            </div>
            <Field label="Skill name">
              <input
                value={skill}
                onChange={(e) =>
                  onSkillsChange(skills.map((value, i) => (i === index ? e.target.value : value)))
                }
                placeholder="Python"
              />
            </Field>
          </div>
        ))}
      </section>

      <section className="profile-section">
        <div className="row-actions">
          <h2>Languages</h2>
          <Button
            variant="ghost"
            onClick={() => onLanguagesChange([...languages, { ...EMPTY_LANGUAGE }])}
          >
            Add language
          </Button>
        </div>
        <p className="muted">Used by Workday auto-apply. Language name is required for each row.</p>
        {languages.length === 0 && <p className="muted">No languages saved yet.</p>}
        {languages.map((row, index) => (
          <div key={`lang-${index}`} className="profile-repeat-card">
            <div className="row-actions">
              <strong>Language {index + 1}</strong>
              <Button
                variant="danger"
                onClick={() => onLanguagesChange(languages.filter((_, i) => i !== index))}
              >
                Remove
              </Button>
            </div>
            <div className="form-grid">
              <Field label="Language">
                <input
                  value={row.language}
                  onChange={(e) =>
                    onLanguagesChange(updateRow(languages, index, { language: e.target.value }))
                  }
                  placeholder="English"
                />
              </Field>
              <Field label="Proficiency">
                <input
                  value={row.proficiency}
                  onChange={(e) =>
                    onLanguagesChange(updateRow(languages, index, { proficiency: e.target.value }))
                  }
                  placeholder="Fluent"
                />
              </Field>
              {/* Field is a <label>; nest only one label around the checkbox. */}
              <div className="field">
                <span className="field-label">Native language</span>
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={row.is_native}
                    onChange={(e) =>
                      onLanguagesChange(
                        updateRow(languages, index, { is_native: e.target.checked }),
                      )
                    }
                  />
                  This is my native language
                </label>
              </div>
            </div>
          </div>
        ))}
      </section>
    </>
  );
}
