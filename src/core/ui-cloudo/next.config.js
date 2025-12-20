/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  compress: true,
  basePath: '',
  assetPrefix: '',
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7071/api'
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: process.env.API_PROXY_URL || 'http://localhost:7071/api/:path*'
      }
    ]
  }
}

module.exports = nextConfig
