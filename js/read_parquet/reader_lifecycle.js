/** Own parquet-wasm handles until their last asynchronous read has settled. */
export class ParquetReaderLifecycle {
  constructor() {
    this.disposed = false;
    this.initialized = false;
    this.parquetFile = null;
    this._initializing = null;
    this._handles = new Map();
  }

  async initialize() {
    if (this.disposed || this.initialized) return;
    if (!this._initializing) {
      this._initializing = this._initialize()
        .then(() => {
          if (!this.disposed) this.initialized = true;
        })
        .finally(() => {
          this._initializing = null;
        });
    }
    await this._initializing;
  }

  async _openParquetFile(pq, url) {
    if (this.disposed) return null;
    const file = await pq.ParquetFile.fromUrl(url);
    if (this.disposed) {
      file.free();
      return null;
    }
    this._handles.set(file, 0);
    return file;
  }

  _releaseParquetFile(file) {
    if (this._handles.get(file) !== 0) return;
    this._handles.delete(file);
    file.free();
  }

  // intoIPCStream consumes the WASM table. When disposed, free it instead
  // so callers cannot decode or cache a late result.
  async _readParquetIPC(file, options, temporary = false) {
    if (!file || this.disposed) {
      this._releaseParquetFile(file);
      return null;
    }
    this._handles.set(file, this._handles.get(file) + 1);
    try {
      const table = await file.read(options);
      if (this.disposed) {
        table.free();
        return null;
      }
      return table.intoIPCStream();
    } finally {
      this._handles.set(file, this._handles.get(file) - 1);
      if (temporary || this.disposed) this._releaseParquetFile(file);
    }
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    for (const file of this._handles.keys()) this._releaseParquetFile(file);
    this.parquetFile = null;
    this.initialized = false;
  }
}
