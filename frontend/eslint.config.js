/* ESLint flat config for the React + TypeScript frontend. */
import js from "@eslint/js";
import tsPlugin from "@typescript-eslint/eslint-plugin";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";

export default [
  // Flat config ignores node_modules by default; the rest mirror the paths the
  // eslintrc `ignorePatterns` carried, plus this file (the old config excluded
  // itself the same way).
  { ignores: ["dist/**", "vite.config.ts", "eslint.config.js"] },
  js.configs.recommended,
  ...tsPlugin.configs["flat/recommended"],
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: { ...globals.browser, ...globals.node, ...globals.es2021 },
    },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "@typescript-eslint/no-explicit-any": "warn",
      // Allow intentionally-unused identifiers prefixed with `_` (e.g. mock
      // signatures kept so `toHaveBeenCalledWith` stays type-checked).
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" },
      ],
    },
  },
];
