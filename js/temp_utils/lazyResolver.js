/**
 * Lightweight Dependency Resolver
 * Breaks circular dependencies with minimal overhead
 */

class LazyResolver {
  constructor() {
    this.cache = new Map();
    this.loading = new Set();
  }

  /**
   * Create a lazy function that imports and caches a module export
   */
  lazy(importFn, exportName = 'default') {
    const key = importFn.toString() + exportName;

    return async (...args) => {
      // Return cached if available
      if (this.cache.has(key)) {
        const cached = this.cache.get(key);
        return typeof cached === 'function' ? cached(...args) : cached;
      }

      // Prevent duplicate loading
      if (this.loading.has(key)) {
        await this.waitForLoad(key);
        return this.lazy(importFn, exportName)(...args);
      }

      // Load the module
      this.loading.add(key);

      try {
        const module = await importFn();
        const exported =
          exportName === 'default' ? module.default : module[exportName];

        if (!exported) {
          throw new Error(`Export '${exportName}' not found`);
        }

        this.cache.set(key, exported);
        return typeof exported === 'function' ? exported(...args) : exported;
      } catch (error) {
        throw new Error(`Failed to load dependency: ${error.message}`);
      } finally {
        this.loading.delete(key);
      }
    };
  }

  /**
   * Create multiple lazy functions at once
   */
  createLazy(imports) {
    const result = {};

    for (const [name, config] of Object.entries(imports)) {
      const { importFn, exportName = 'default' } = config;
      result[name] = this.lazy(importFn, exportName);
    }

    return result;
  }

  /**
   * Wait for a module to finish loading
   */
  async waitForLoad(key, timeout = 5000) {
    const start = Date.now();

    while (this.loading.has(key)) {
      if (Date.now() - start > timeout) {
        throw new Error('Timeout waiting for module to load');
      }
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
  }

  /**
   * Clear cache (useful for testing)
   */
  clear() {
    this.cache.clear();
    this.loading.clear();
  }

  /**
   * Get cache stats
   */
  stats() {
    return {
      cached: this.cache.size,
      loading: this.loading.size,
    };
  }
}

// Create default instance
export const resolver = new LazyResolver();

// Convenience function for quick usage
export const lazy = (importFn, exportName) =>
  resolver.lazy(importFn, exportName);

// Batch creation helper
export const createLazy = (imports) => resolver.createLazy(imports);
