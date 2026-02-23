/** @type {import('next').NextConfig} */
const nextConfig = {
  // Serve existing static HTML at /index.html and /blog.html
  async rewrites() {
    return [];
  },
};

module.exports = nextConfig;
