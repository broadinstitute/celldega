// Jest setup file - CommonJS format
require('@testing-library/jest-dom');

// jsdom omits TextEncoder/TextDecoder, which apache-arrow touches at import time. Browsers
// have had both for years, so this is filling a jsdom gap rather than mocking anything.
const { TextDecoder, TextEncoder } = require('util');
if (typeof global.TextDecoder === 'undefined') global.TextDecoder = TextDecoder;
if (typeof global.TextEncoder === 'undefined') global.TextEncoder = TextEncoder;

// Mock browser APIs that your code might use
global.console = {
  ...console,
  // Suppress console.warn in tests unless needed
  warn: jest.fn(),
};

// Mock fetch if your code uses it
global.fetch = jest.fn();

// Mock window.URL if needed for your project
global.URL = {
  createObjectURL: jest.fn(),
  revokeObjectURL: jest.fn(),
};

// Reset all mocks after each test
afterEach(() => {
  jest.clearAllMocks();
});
