/* global require */

const fs = require('fs');
const path = require('path');

const readSource = (name) =>
  fs
    .readFileSync(path.join(__dirname, '../read_parquet', name), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export (class|async function|function)/gm, '$1')
    .replace(/^export default .*;$/gm, '');
const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

describe('Parquet reader disposal', () => {
  let classes;
  let pq;
  let arrow;
  let files;
  let makeFile;
  const zoomInfo = {
    0: { row_group_offset: 0, num_tiles_x: 2, num_tiles_y: 1 },
  };

  beforeEach(() => {
    files = [];
    makeFile = () => {
      const file = {
        free: jest.fn(),
        metadata: () => ({ numRowGroups: () => 2, free: jest.fn() }),
        read: jest.fn(async () => ({
          intoIPCStream: () => new Uint8Array([1]),
          free: jest.fn(),
        })),
      };
      files.push(file);
      return file;
    };
    pq = { ParquetFile: { fromUrl: jest.fn(async () => makeFile()) } };
    arrow = {
      tableFromIPC: jest.fn(() => ({
        schema: { metadata: new Map([['gene_to_row_group', '{"G":0}']]) },
        getChild: () => ({ length: 1, get: () => new Uint8Array([1, 2]) }),
      })),
    };
    classes = new Function(
      'getPq',
      'arrow',
      'concatenate_arrow_tables',
      `
      ${readSource('reader_lifecycle.js')}
      ${readSource('image_row_group_reader.js')}
      ${readSource('row_group_tile_reader.js')}
      ${readSource('cbg_row_group_reader.js')}
      return { ImageRowGroupReader, RowGroupTileReader, CBGRowGroupReader };
    `
    )(
      async () => pq,
      arrow,
      (tables) => tables
    );
    URL.createObjectURL = jest.fn(() => 'blob:tile');
    URL.revokeObjectURL = jest.fn();
    jest.spyOn(console, 'log').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
  });
  afterEach(() => jest.restoreAllMocks());

  const makeReader = (kind, chunked) => {
    const config = chunked
      ? {
          directory: 'tiles',
          files: ['0.parquet', '1.parquet'],
          max_row_groups_per_file: 1,
          gene_to_row_group: { G: 0 },
          zoom_info: zoomInfo,
        }
      : 'tiles.parquet';
    const reader =
      kind === 'image'
        ? new classes.ImageRowGroupReader('http://localhost', config, zoomInfo)
        : kind === 'tile'
          ? new classes.RowGroupTileReader(
              'http://localhost',
              { num_tiles_x: 2, num_tiles_y: 1 },
              config
            )
          : new classes.CBGRowGroupReader('http://localhost', config);
    reader._checkRangeSupport = async () => true;
    reader._resourceExists = async () => true;
    return reader;
  };
  const read = (reader, kind) =>
    kind === 'image'
      ? reader.readTile(0, 0, 0)
      : kind === 'tile'
        ? reader.readTiles([{ tile_x: 0, tile_y: 0 }])
        : reader.readGene('G');

  test.each(['image', 'tile', 'gene'])(
    '%s: disposal just after opening cannot reinstall a freed persistent handle',
    async (kind) => {
      const reader = makeReader(kind, false);
      const open = reader._openParquetFile.bind(reader);
      reader._openParquetFile = async (...args) => {
        const file = await open(...args);
        reader.dispose();
        return file;
      };
      await reader.initialize();
      expect(reader.parquetFile).toBeNull();
      expect(reader.initialized).toBe(false);
      expect(files[0].free).toHaveBeenCalledTimes(1);
    }
  );

  test.each(['image', 'tile', 'gene'])(
    '%s: disposal during initialization frees a late handle and prevents reopening',
    async (kind) => {
      const reader = makeReader(kind, false);
      const opened = deferred();
      const started = deferred();
      const file = makeFile();
      pq.ParquetFile.fromUrl.mockImplementation(() => {
        started.resolve();
        return opened.promise;
      });
      const first = reader.initialize();
      const second = reader.initialize();
      await started.promise;
      reader.dispose();
      opened.resolve(file);
      await Promise.all([first, second]);
      expect(file.free).toHaveBeenCalledTimes(1);
      expect(reader.initialized).toBe(false);
      expect(reader.parquetFile).toBeNull();
      await expect(read(reader, kind)).resolves.toBeNull();
      await reader.initialize();
      expect(pq.ParquetFile.fromUrl).toHaveBeenCalledTimes(1);
    }
  );

  test.each(
    ['image', 'tile', 'gene'].flatMap((kind) =>
      [false, true].map((chunked) => [kind, chunked])
    )
  )(
    '%s: disposal during read (chunked=%s) drains safely without publishing a result',
    async (kind, chunked) => {
      const reader = makeReader(kind, chunked);
      await reader.initialize();
      if (kind === 'gene') reader.geneToRowGroup = { G: 0 };
      const file = chunked ? makeFile() : reader.parquetFile;
      if (chunked) pq.ParquetFile.fromUrl.mockResolvedValue(file);
      const pending = deferred();
      const started = deferred();
      file.read.mockImplementation(() => {
        started.resolve();
        return pending.promise;
      });
      const result = read(reader, kind);
      await started.promise;
      reader.dispose();
      reader.dispose();
      expect(file.free).not.toHaveBeenCalled();
      const table = { free: jest.fn(), intoIPCStream: jest.fn() };
      pending.resolve(table);
      await expect(result).resolves.toBeNull();
      expect(file.free).toHaveBeenCalledTimes(1);
      expect(table.free).toHaveBeenCalledTimes(1);
      expect(table.intoIPCStream).not.toHaveBeenCalled();
      expect(reader.blobCache?.size || reader.requestCache?.size || 0).toBe(0);
      expect(URL.createObjectURL).not.toHaveBeenCalled();
      await expect(read(reader, kind)).resolves.toBeNull();
    }
  );

  test.each(
    ['image', 'tile', 'gene'].flatMap((kind) =>
      [false, true].map((fails) => [kind, fails])
    )
  )(
    '%s: temporary chunk handles are freed (failure=%s)',
    async (kind, fails) => {
      const reader = makeReader(kind, true);
      await reader.initialize();
      const file = makeFile();
      pq.ParquetFile.fromUrl.mockResolvedValue(file);
      if (fails) file.read.mockRejectedValue(new Error('read failed'));
      const result = await read(reader, kind);
      if (fails) expect(result).toBeNull();
      else expect(result).not.toBeNull();
      expect(file.free).toHaveBeenCalledTimes(1);
      reader.dispose();
      expect(file.free).toHaveBeenCalledTimes(1);
    }
  );

  test('concurrent image reads reuse the cached URL and disposal revokes it', async () => {
    const reader = makeReader('image', true);
    await reader.initialize();
    const results = await Promise.all([
      read(reader, 'image'),
      read(reader, 'image'),
    ]);
    expect(results).toEqual(['blob:tile', 'blob:tile']);
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    expect(files).toHaveLength(2);
    files.forEach((file) => expect(file.free).toHaveBeenCalledTimes(1));
    reader.dispose();
    reader.dispose();
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1);
  });

  test.each(['image', 'gene'])(
    '%s: metadata probe handles are freed',
    async (kind) => {
      const reader = makeReader(kind, true);
      if (kind === 'image') await reader._loadZoomInfoFromParquetMetadata(pq);
      else await reader._discoverChunkedCbgFromDefaultDirectory(pq);
      expect(files).toHaveLength(1);
      expect(files[0].free).toHaveBeenCalledTimes(1);
    }
  );

  test('disposing during lazy gene-index loading cannot restore the index', async () => {
    const reader = makeReader('gene', false);
    await reader.initialize();
    const pending = deferred();
    const started = deferred();
    const file = reader.parquetFile;
    file.read.mockImplementation(() => {
      started.resolve();
      return pending.promise;
    });
    const result = reader.readGene('G');
    await started.promise;
    reader.dispose();
    pending.resolve({ free: jest.fn() });
    await expect(result).resolves.toBeNull();
    expect(reader.geneToRowGroup).toBeNull();
    expect(reader.geneList).toBeNull();
    expect(file.free).toHaveBeenCalledTimes(1);
  });
});
