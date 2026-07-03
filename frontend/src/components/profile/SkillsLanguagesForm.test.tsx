import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { LanguageEntry } from "../../types";
import { EMPTY_LANGUAGE, SkillsLanguagesForm } from "./SkillsLanguagesForm";

function makeLang(overrides: Partial<LanguageEntry> = {}): LanguageEntry {
  return { ...EMPTY_LANGUAGE, ...overrides };
}

function renderForm(props: Partial<React.ComponentProps<typeof SkillsLanguagesForm>> = {}) {
  const onSkillsChange = vi.fn();
  const onLanguagesChange = vi.fn();
  render(
    <SkillsLanguagesForm
      skills={props.skills ?? []}
      languages={props.languages ?? []}
      onSkillsChange={props.onSkillsChange ?? onSkillsChange}
      onLanguagesChange={props.onLanguagesChange ?? onLanguagesChange}
    />,
  );
  return { onSkillsChange, onLanguagesChange };
}

describe("SkillsLanguagesForm", () => {
  it("shows empty-state hints for both sections", () => {
    renderForm();

    expect(screen.getByText("No skills saved yet.")).toBeInTheDocument();
    expect(screen.getByText("No languages saved yet.")).toBeInTheDocument();
  });

  it("adds a blank skill", () => {
    const { onSkillsChange } = renderForm({ skills: ["Python"] });

    fireEvent.click(screen.getByRole("button", { name: "Add skill" }));

    expect(onSkillsChange).toHaveBeenCalledWith(["Python", ""]);
  });

  it("edits a skill value", () => {
    const { onSkillsChange } = renderForm({ skills: ["Python", "Go"] });

    fireEvent.change(screen.getAllByPlaceholderText("Python")[1], { target: { value: "Rust" } });

    expect(onSkillsChange).toHaveBeenCalledWith(["Python", "Rust"]);
  });

  it("removes the skill at the clicked index", () => {
    const { onSkillsChange } = renderForm({ skills: ["Python", "Go"] });

    const removeButtons = screen.getAllByRole("button", { name: "Remove" });
    fireEvent.click(removeButtons[0]);

    expect(onSkillsChange).toHaveBeenCalledWith(["Go"]);
  });

  it("adds a blank language", () => {
    const { onLanguagesChange } = renderForm({ languages: [makeLang({ language: "English" })] });

    fireEvent.click(screen.getByRole("button", { name: "Add language" }));

    expect(onLanguagesChange).toHaveBeenCalledWith([
      makeLang({ language: "English" }),
      { ...EMPTY_LANGUAGE },
    ]);
  });

  it("edits language fields and the native checkbox", () => {
    const { onLanguagesChange } = renderForm({ languages: [makeLang()] });

    fireEvent.change(screen.getByPlaceholderText("English"), { target: { value: "French" } });
    expect(onLanguagesChange).toHaveBeenLastCalledWith([makeLang({ language: "French" })]);

    fireEvent.change(screen.getByPlaceholderText("Fluent"), { target: { value: "Native" } });
    expect(onLanguagesChange).toHaveBeenLastCalledWith([makeLang({ proficiency: "Native" })]);

    fireEvent.click(screen.getByLabelText("This is my native language"));
    expect(onLanguagesChange).toHaveBeenLastCalledWith([makeLang({ is_native: true })]);
  });

  it("removes the language at the clicked index", () => {
    const { onLanguagesChange } = renderForm({
      languages: [makeLang({ language: "English" }), makeLang({ language: "French" })],
    });

    const removeButtons = screen.getAllByRole("button", { name: "Remove" });
    fireEvent.click(removeButtons[1]);

    expect(onLanguagesChange).toHaveBeenCalledWith([makeLang({ language: "English" })]);
  });

  it("only patches the edited language row, leaving others untouched", () => {
    const rows = [makeLang({ language: "English" }), makeLang({ language: "French" })];
    const { onLanguagesChange } = renderForm({ languages: rows });

    fireEvent.change(screen.getAllByPlaceholderText("English")[1], {
      target: { value: "Français" },
    });

    expect(onLanguagesChange).toHaveBeenCalledWith([
      makeLang({ language: "English" }),
      makeLang({ language: "Français" }),
    ]);
  });

  it("labels rows by their 1-based index", () => {
    renderForm({ skills: ["a", "b"], languages: [makeLang(), makeLang()] });

    expect(screen.getByText("Skill 1")).toBeInTheDocument();
    expect(screen.getByText("Skill 2")).toBeInTheDocument();
    expect(screen.getByText("Language 1")).toBeInTheDocument();
    expect(screen.getByText("Language 2")).toBeInTheDocument();
  });
});
