import js from '@eslint/js';
import importPlugin from 'eslint-plugin-import';
import prettierConfig from 'eslint-config-prettier';
import globals from 'globals';

export default [
  // Base configuration
  js.configs.recommended,

  // Prettier config to disable conflicting rules
  prettierConfig,

  // File targeting - only your js/ directory
  {
    files: ['js/**/*.js', 'js/**/*.mjs'],
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: 'module',
      // Include all browser globals (from your original config) + additional ones
      globals: {
        ...globals.browser,  // All browser globals (window, document, fetch, etc.)
        ...globals.es2024,   // Modern JS globals
        // Additional Node.js globals for build tools/development
        process: 'readonly',
        Buffer: 'readonly',
        __dirname: 'readonly',
        __filename: 'readonly',
        global: 'readonly'
      }
    },
    plugins: {
      import: importPlugin
    },
    rules: {
      // Import ordering rules - This is what you wanted!
      'import/order': [
        'error',
        {
          'groups': [
            'builtin',      // Node.js built-in modules (fs, path, etc.)
            'external',     // npm packages (lodash, express, etc.)
            'internal',     // Internal modules (your project modules)
            'parent',       // ../something
            'sibling',      // ./something
            'index'         // ./index.js
          ],
          'newlines-between': 'always',
          'alphabetize': {
            'order': 'asc',
            'caseInsensitive': true
          },
          'pathGroups': [
            {
              'pattern': '@/**',
              'group': 'internal',
              'position': 'before'
            }
          ],
          'pathGroupsExcludedImportTypes': ['builtin']
        }
      ],
      'import/no-unresolved': ['error', {
        'ignore': ['^@/'] // Ignore alias imports if you use them
      }],
      'import/no-duplicates': 'error',
      'import/first': 'error',
      'import/newline-after-import': 'error',
      'import/no-unused-modules': 'warn',
      'import/extensions': ['error', 'ignorePackages', {
        'js': 'never',
        'mjs': 'never'
      }],
      'import/no-cycle': 'error', // Prevent circular dependencies
      'no-restricted-imports': ['error', {
        'patterns': ['../**/index'] // Prevent deep relative imports
      }],

      // General code quality rules (no formatting rules - Prettier handles those)
      'no-unused-vars': ['error', {
        'argsIgnorePattern': '^_',
        'varsIgnorePattern': '^_'
      }],
      'no-console': 'warn',
      'prefer-const': 'error',
      'no-var': 'error',
      'object-shorthand': 'error',
      'prefer-template': 'error',
      'no-undef': 'error',
      'no-duplicate-imports': 'error',

      // Additional quality rules for modern JS
      'no-unused-expressions': 'error',
      'no-implicit-globals': 'error',
      'no-shadow': 'warn',
      'no-use-before-define': ['error', { 'functions': false }],
      'prefer-arrow-callback': 'warn',
      'prefer-destructuring': ['warn', {
        'array': false,
        'object': true
      }],

      // Async/Promise best practices
      'no-async-promise-executor': 'error',
      'no-await-in-loop': 'warn',
      'prefer-promise-reject-errors': 'error',

      // ES6+ best practices
      'no-useless-constructor': 'error',
      'no-useless-rename': 'error',
      'object-curly-spacing': 'off', // Handled by Prettier
      'array-bracket-spacing': 'off' // Handled by Prettier
    }
  },

  // Special configuration for test files
  {
    files: ['js/**/*.test.js', 'js/**/*.spec.js'],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.es2024,
        ...globals.jest,  // Jest globals (describe, test, expect, etc.)
      }
    },
    rules: {
      'no-console': 'off', // Allow console in tests
      'import/no-unresolved': 'off', // Tests might import test utilities
    }
  },

  // Special configuration for build files (less strict)
  {
    files: ['build.js', 'wasm-plugin.mjs'],
    languageOptions: {
      globals: {
        ...globals.node,
        ...globals.es2024
      }
    },
    rules: {
      'no-console': 'off', // Allow console in build files
      'import/no-unresolved': 'off' // Build files might import dynamic modules
    }
  },

  // Ignore patterns
  {
    ignores: [
      'node_modules/**',
      'dist/**',
      '.history/**',
      'src/**',
      'notebooks/**',
      '*.html',
      'js/vendor/**' // Also ignore vendor directory as per your package.json
    ]
  }
];
