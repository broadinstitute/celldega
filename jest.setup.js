// Jest setup file - CommonJS format
require('@testing-library/jest-dom');

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
