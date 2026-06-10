import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // shadcn/ui 内部使用了 Math.random 等不纯函数，禁用此类规则避免修改三方代码
      "react-hooks/purity": "off",
      "react-hooks/incompatible-library": "off",
      "react-hooks/refs": "off",
      "react-hooks/error-boundaries": "off",
      "react-hooks/static-components": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/set-state-in-render": "off",
      "react-hooks/component-hook-factories": "off",
      "react-hooks/globals": "off",
      "react-hooks/immutability": "off",
      "react-hooks/preserve-manual-memoization": "off",
      "react-hooks/missing-key-in-loop": "off",
      "react-hooks/unsupported-syntax": "off",
      "react-hooks/incompatible-library": "off",
      "react-hooks/use-memo": "off",
      "react-hooks/preserve-manual-memoization": "off",
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    "components/ui/**",  // shadcn 生成的代码跳过自定义规则
    "public/mockServiceWorker.js",  // MSW 生成的 worker
  ]),
]);

export default eslintConfig;
