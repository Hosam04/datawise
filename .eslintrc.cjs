const nextConfig = require("eslint-config-next/core-web-vitals");
module.exports = [
  ...nextConfig,
  {
    ignores: [
      "**/.next/**",
      "**/node_modules/**",
      "**/backend/**",
      "**/venv/**",
      "**/storage/**",
      "**/*.tsbuildinfo",
      "**/package-lock.json",
      "**/pnpm-lock.yaml",
    ],
  },
];
