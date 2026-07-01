/** Promo code entry with optional validation before checkout. */

import { useState } from "react";
import { api } from "../api";
import type { PromoValidation } from "../types";
import { Banner, Button, Field } from "./ui";

type Props = {
  onApplied: (promo: PromoValidation | null) => void;
  disabled?: boolean;
};

export function PromoCodeField({ onApplied, disabled }: Props) {
  const [code, setCode] = useState("");
  const [applied, setApplied] = useState<PromoValidation | null>(null);
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  async function applyCode() {
    const trimmed = code.trim();
    if (!trimmed) {
      setApplied(null);
      onApplied(null);
      setError(undefined);
      return;
    }
    setBusy(true);
    setError(undefined);
    try {
      const result = await api.validatePromoCode(trimmed);
      setApplied(result);
      onApplied(result);
    } catch (err) {
      setApplied(null);
      onApplied(null);
      setError(err instanceof Error ? err.message : "Invalid promo code.");
    } finally {
      setBusy(false);
    }
  }

  function clearCode() {
    setCode("");
    setApplied(null);
    onApplied(null);
    setError(undefined);
  }

  return (
    <div className="promo-code-field">
      <Field label="Promo code">
        <div className="promo-code-row">
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="Enter code"
            disabled={disabled || busy}
            aria-label="Promo code"
          />
          <Button
            type="button"
            variant="ghost"
            onClick={() => void applyCode()}
            disabled={disabled || busy || !code.trim()}
          >
            {busy ? "Checking…" : "Apply"}
          </Button>
        </div>
      </Field>
      {applied ? (
        <p className="promo-code-applied" role="status">
          Applied: <strong>{applied.description}</strong>{" "}
          <button type="button" className="link-button" onClick={clearCode}>
            Remove
          </button>
        </p>
      ) : null}
      {error ? <Banner kind="error">{error}</Banner> : null}
    </div>
  );
}
