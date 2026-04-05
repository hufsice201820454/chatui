import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 개발 시 화면에 뜨는 드래그 가능한 N 버튼(Next.js dev indicator) 비활성화
  devIndicators: false,
  async rewrites() {
    // FastAPI 직접 호출 프록시 (파일 업로드, 세션 관리 등)
    return [
      {
        source: "/backend/:path*",
        destination: `${process.env.BACKEND_URL ?? "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
