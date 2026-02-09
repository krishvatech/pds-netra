/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      { protocol: 'http', hostname: '**' },
      { protocol: 'https', hostname: '**' }
    ]
  },
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Referrer-Policy', value: 'no-referrer' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' }
        ]
      }
    ];
  },
  async rewrites() {
    const backend = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8001';
    return [
      // Proxy backend APIs through Next.js to avoid CORS in local dev.
      { source: '/api/:path*', destination: `${backend}/api/:path*` },
      { source: '/media/:path*', destination: `${backend}/media/:path*` }
    ];
  }
};

export default nextConfig;
