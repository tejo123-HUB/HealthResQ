/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack: (config) => {
    // libsodium-wrappers' ESM build ("module" field) does a broken relative import
    // ("./libsodium.mjs") that only exists in the sibling `libsodium` package, not alongside
    // itself — a known packaging bug. Force webpack to the CJS build instead, which requires
    // "libsodium" as a normal package specifier and resolves fine.
    config.resolve.alias = {
      ...config.resolve.alias,
      "libsodium-wrappers$": require.resolve("libsodium-wrappers"),
    };
    return config;
  },
};

module.exports = nextConfig;
