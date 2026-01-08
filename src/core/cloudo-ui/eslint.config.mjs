import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  {
    ignores: [
      ".next/**",
      "out/**",
      "build/**",
      "next-env.d.ts",
      "postcss.config.js",
      "tailwind.config.js",
    ],
  },
  ...nextVitals.map((config) => ({
    ...config,
    rules: {
      ...config.rules,
      "@next/next/no-html-link-for-pages": ["error", "src/core/cloudo-ui/app"],
    },
  })),
  ...nextTs,
]);

export default eslintConfig;
