/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  images: {
    unoptimized: true,
  },
  compress: true,
  env: {
    FUNCTION_API_URL: process.env.FUNCTION_API_URL || '/api'
  }
}

module.exports = nextConfig
