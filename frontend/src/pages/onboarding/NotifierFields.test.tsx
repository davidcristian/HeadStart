import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { must } from "../../test/must";
import { NotifierFields } from "./NotifierFields";
import { NOTIFIER_HINTS } from "./constants";
import type { Json } from "../../types";

describe("NotifierFields", () => {
  it("renders ntfy fields with defaults and reports changes", () => {
    const onChange = vi.fn();
    render(<NotifierFields notifierType="ntfy" config={{}} onChange={onChange} />);

    expect(screen.getByText("ntfy topic")).toBeInTheDocument();
    expect(screen.getByText(NOTIFIER_HINTS.ntfy)).toBeInTheDocument();

    const topic = screen.getByPlaceholderText("my-job-alerts") as HTMLInputElement;
    expect(topic.value).toBe("");
    const serverUrl = screen.getByDisplayValue("https://ntfy.sh") as HTMLInputElement;
    expect(serverUrl.value).toBe("https://ntfy.sh");

    fireEvent.change(topic, { target: { value: "jobs" } });
    expect(onChange).toHaveBeenLastCalledWith({ topic: "jobs" });

    fireEvent.change(serverUrl, { target: { value: "https://n.example" } });
    expect(onChange).toHaveBeenLastCalledWith({ server_url: "https://n.example" });
  });

  it("renders ntfy fields with provided config values", () => {
    const config: Json = { topic: "alerts", server_url: "https://self.host" };
    render(<NotifierFields notifierType="ntfy" config={config} onChange={vi.fn()} />);

    expect((screen.getByPlaceholderText("my-job-alerts") as HTMLInputElement).value).toBe("alerts");
    expect((screen.getByDisplayValue("https://self.host") as HTMLInputElement).value).toBe(
      "https://self.host",
    );
  });

  it("renders the email field and reports changes", () => {
    const onChange = vi.fn();
    render(<NotifierFields notifierType="email" config={{}} onChange={onChange} />);

    expect(screen.getByText("Recipient email")).toBeInTheDocument();
    expect(screen.getByText(NOTIFIER_HINTS.email)).toBeInTheDocument();

    const input = screen.getByPlaceholderText("you@example.com") as HTMLInputElement;
    expect(input.type).toBe("email");
    expect(input.value).toBe("");

    fireEvent.change(input, { target: { value: "me@example.com" } });
    expect(onChange).toHaveBeenLastCalledWith({ to: "me@example.com" });
  });

  it("renders the email field with a provided value", () => {
    render(<NotifierFields notifierType="email" config={{ to: "a@b.co" }} onChange={vi.fn()} />);
    expect((screen.getByPlaceholderText("you@example.com") as HTMLInputElement).value).toBe(
      "a@b.co",
    );
  });

  it("renders the slack webhook field and reports changes", () => {
    const onChange = vi.fn();
    render(<NotifierFields notifierType="slack" config={{}} onChange={onChange} />);

    expect(screen.getByText("Webhook URL")).toBeInTheDocument();
    expect(screen.getByText(NOTIFIER_HINTS.slack)).toBeInTheDocument();

    const input = screen.getByPlaceholderText("https://...") as HTMLInputElement;
    expect(input.value).toBe("");
    fireEvent.change(input, { target: { value: "https://hooks.slack" } });
    expect(onChange).toHaveBeenLastCalledWith({ webhook_url: "https://hooks.slack" });
  });

  it("renders the discord webhook field with its hint and a provided value", () => {
    render(
      <NotifierFields
        notifierType="discord"
        config={{ webhook_url: "https://discord.hook" }}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByText(NOTIFIER_HINTS.discord)).toBeInTheDocument();
    expect((screen.getByPlaceholderText("https://...") as HTMLInputElement).value).toBe(
      "https://discord.hook",
    );
  });

  it("renders telegram fields with defaults and reports changes", () => {
    const onChange = vi.fn();
    render(<NotifierFields notifierType="telegram" config={{}} onChange={onChange} />);

    expect(screen.getByText("Bot token")).toBeInTheDocument();
    expect(screen.getByText("Chat id")).toBeInTheDocument();
    expect(screen.getByText(NOTIFIER_HINTS.telegram)).toBeInTheDocument();

    const inputs = screen.getAllByRole("textbox") as HTMLInputElement[];
    const botToken = must(inputs[0]);
    const chatId = must(inputs[1]);
    expect(botToken.value).toBe("");
    expect(chatId.value).toBe("");

    fireEvent.change(botToken, { target: { value: "123:abc" } });
    expect(onChange).toHaveBeenLastCalledWith({ bot_token: "123:abc" });

    fireEvent.change(chatId, { target: { value: "999" } });
    expect(onChange).toHaveBeenLastCalledWith({ chat_id: "999" });
  });

  it("renders telegram fields with provided config values", () => {
    render(
      <NotifierFields
        notifierType="telegram"
        config={{ bot_token: "tok", chat_id: "42" }}
        onChange={vi.fn()}
      />,
    );

    expect((screen.getByDisplayValue("tok") as HTMLInputElement).value).toBe("tok");
    expect((screen.getByDisplayValue("42") as HTMLInputElement).value).toBe("42");
  });

  it("falls back to the generic webhook field for unknown types", () => {
    const onChange = vi.fn();
    render(<NotifierFields notifierType="webhook" config={{}} onChange={onChange} />);

    expect(screen.getByText("Webhook URL")).toBeInTheDocument();
    expect(screen.getByText(NOTIFIER_HINTS.webhook)).toBeInTheDocument();

    const input = screen.getByPlaceholderText("https://...") as HTMLInputElement;
    expect(input.value).toBe("");
    fireEvent.change(input, { target: { value: "https://custom.hook" } });
    expect(onChange).toHaveBeenLastCalledWith({ webhook_url: "https://custom.hook" });
  });

  it("renders the generic webhook field with a provided value for an entirely unknown type", () => {
    render(
      <NotifierFields
        notifierType="mystery"
        config={{ webhook_url: "https://kept.hook" }}
        onChange={vi.fn()}
      />,
    );
    expect((screen.getByPlaceholderText("https://...") as HTMLInputElement).value).toBe(
      "https://kept.hook",
    );
  });
});
