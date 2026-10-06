/** @type {import('next').NextConfig} */
const nextConfig = {
  output: process.env.NEXT_OUTPUT === "export" ? "export" : "standalone",
  trailingSlash: process.env.NEXT_OUTPUT === "export",
  async headers() {
    if (process.env.NEXT_OUTPUT === "export") return [];
    return [{ source: "/:path*", headers: [
      { key: "Referrer-Policy", value: "no-referrer" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
    ] }];
  },
};

export default nextConfig;
