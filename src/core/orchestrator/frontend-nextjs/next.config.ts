/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  compress: true,
  basePath: '/app',
  assetPrefix: '/app',
  env: {
    FUNCTION_API_URL: process.env.FUNCTION_API_URL || '/api'
  }
}

module.exports = nextConfig
