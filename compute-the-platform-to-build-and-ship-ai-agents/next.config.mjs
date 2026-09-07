/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://127.0.0.1:8000/api/v1/:path*',
      },
      {
        source: '/healthz',
        destination: 'http://127.0.0.1:8000/healthz',
      },
      {
        source: '/static/exports/:path*',
        destination: 'http://127.0.0.1:8000/static/exports/:path*',
      },
    ];
  },
}

export default nextConfig
