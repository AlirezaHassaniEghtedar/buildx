import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // standalone فقط برای بیلد داکر (BUILD_STANDALONE=1 در web.Dockerfile).
  // R20: بیلد محلی روی ویندوز بدون Developer Mode ممکن است با EPERM symlink بشکند.
  ...(process.env.BUILD_STANDALONE === "1" ? { output: "standalone" as const } : {}),
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    return [
      { source: "/api/:path*", destination: `${api}/api/:path*` },
      { source: "/healthz", destination: `${api}/healthz` },
    ];
  },
};

export default nextConfig;
