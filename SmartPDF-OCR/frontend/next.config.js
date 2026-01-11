/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'export',
  images: {
    unoptimized: true,
  },
  // Disable server-side features for static export
  trailingSlash: true,
  // Ensure assets load correctly in Electron (file:// protocol)
  assetPrefix: './',
};

module.exports = nextConfig;
