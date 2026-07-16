import eslint from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  {
    ignores: ["dist/**"],
    languageOptions: { globals: { window: "readonly", document: "readonly", navigator: "readonly", localStorage: "readonly", crypto: "readonly", fetch: "readonly", FormData: "readonly", File: "readonly", RequestInit: "readonly", Response: "readonly", Headers: "readonly", URL: "readonly", setTimeout: "readonly", clearTimeout: "readonly" } },
    rules: { "@typescript-eslint/no-explicit-any": "error" },
  },
);
