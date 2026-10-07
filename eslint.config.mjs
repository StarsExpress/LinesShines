import js from "@eslint/js";
import globals from "globals";
import prettier from "eslint-config-prettier";

export default [
  { ignores: ["frontend/vendor/**", "node_modules/**"] },
  js.configs.recommended,
  {
    files: ["frontend/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: { ...globals.browser, Plotly: "readonly", html2canvas: "readonly" },
    },
  },
  {
    files: ["frontend/sw.js"],
    languageOptions: {
      sourceType: "script",
      globals: { ...globals.serviceworker },
    },
  },
  // Last: turns off ESLint rules that conflict with Prettier's formatting.
  prettier,
];
