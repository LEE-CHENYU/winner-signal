import type { NextConfig } from "next";
const config: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination:
          (process.env.API_INTERNAL_URL || "http://127.0.0.1:8000") +
          "/api/:path*",
      },
    ];
  },
  experimental: { proxyClientMaxBodySize: "85mb" },
};
export default config;
