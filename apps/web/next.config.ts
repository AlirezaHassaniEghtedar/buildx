import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // خروجی standalone برای ایمیج سبک داکر (بدون node_modules کامل)
  output: "standalone",
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    return [
      { source: "/api/:path*", destination: `${api}/api/:path*` },
      { source: "/healthz", destination: `${api}/healthz` },
    ];
  },
};

export default nextConfig;
