import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // @bi-copilot/contracts (packages/contracts) is a workspace package
  // consumed directly as TypeScript source, no build step -- Next.js only
  // transpiles code under apps/web/src by default, so packages outside it
  // need to be listed explicitly.
  transpilePackages: ["@bi-copilot/contracts"],
};

export default nextConfig;
