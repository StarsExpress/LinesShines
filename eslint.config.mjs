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
  {
    files: ["tests/js/**/*.mjs"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      // The tests install a fake browser, and read the globals it sets.
      globals: { ...globals.node, ...globals.browser, Plotly: "writable" },
    },
  },
  // Last: turns off ESLint rules that conflict with Prettier's formatting.
  prettier,
];
