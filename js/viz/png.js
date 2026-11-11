// Portable screenshot records live in a PNG iTXt chunk named "celldega".
// This is the same record written by Python's screenshots.py (schema 3).
const PNG_SIGNATURE = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]);
const MAX_PNG_BYTES = 128 * 1024 * 1024;
const MAX_METADATA_BYTES = 64 * 1024 * 1024;
const KEY = 'celldega';
const encoder = new TextEncoder();
const decoder = new TextDecoder('utf-8', { fatal: true });

const crc32 = (bytes) => {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let i = 0; i < 8; i++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return (crc ^ 0xffffffff) >>> 0;
};

const join = (parts) => {
  const output = new Uint8Array(parts.reduce((n, part) => n + part.length, 0));
  let offset = 0;
  for (const part of parts) {
    output.set(part, offset);
    offset += part.length;
  }
  return output;
};

const chunks = (bytes) => {
  if (bytes.length > MAX_PNG_BYTES) throw new Error('PNG exceeds 128 MiB');
  if (PNG_SIGNATURE.some((value, i) => bytes[i] !== value))
    throw new Error('Not a PNG file');
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const result = [];
  let offset = 8;
  while (offset + 12 <= bytes.length) {
    const length = view.getUint32(offset);
    const end = offset + 12 + length;
    if (end > bytes.length) throw new Error('Truncated PNG chunk');
    const type = String.fromCharCode(...bytes.subarray(offset + 4, offset + 8));
    if (crc32(bytes.subarray(offset + 4, end - 4)) !== view.getUint32(end - 4))
      throw new Error(`Invalid PNG ${type} checksum`);
    result.push({
      type,
      data: bytes.subarray(offset + 8, end - 4),
      raw: bytes.subarray(offset, end),
    });
    offset = end;
    if (type === 'IEND') break;
  }
  if (
    result[0]?.type !== 'IHDR' ||
    result[0].data.length !== 13 ||
    result.at(-1)?.type !== 'IEND' ||
    offset !== bytes.length
  )
    throw new Error('Incomplete PNG structure');
  return result;
};

const chunk = (type, data) => {
  const bytes = new Uint8Array(data.length + 12);
  const view = new DataView(bytes.buffer);
  view.setUint32(0, data.length);
  bytes.set(encoder.encode(type), 4);
  bytes.set(data, 8);
  view.setUint32(data.length + 8, crc32(bytes.subarray(4, data.length + 8)));
  return bytes;
};

const keyword = (data) => {
  const end = data.indexOf(0);
  return end < 0
    ? ''
    : String.fromCharCode(...data.subarray(0, Math.min(end, 80)));
};

const bounded_inflate = async (bytes) => {
  if (typeof DecompressionStream !== 'function')
    throw new Error('This browser cannot read compressed PNG metadata');
  const stream = new Blob([bytes])
    .stream()
    .pipeThrough(new DecompressionStream('deflate'));
  const reader = stream.getReader();
  const parts = [];
  let size = 0;
  try {
    while (true) {
      // eslint-disable-next-line no-await-in-loop
      const { value, done } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > MAX_METADATA_BYTES)
        throw new Error('PNG metadata exceeds 64 MiB');
      parts.push(value);
    }
  } finally {
    await reader.cancel();
  }
  return join(parts);
};

export const validate_png_record = (record) => {
  if (
    !record ||
    record.celldega_screenshot !== 3 ||
    !Array.isArray(record.widgets) ||
    !record.widgets.length
  )
    throw new Error(
      'Unsupported Celldega PNG record; expected screenshot schema 3'
    );
  return record;
};

/** Read a browser File/Blob, ArrayBuffer or Uint8Array, including Python's compressed iTXt. */
export const read_png = async (input) => {
  if (input?.size > MAX_PNG_BYTES || input?.byteLength > MAX_PNG_BYTES)
    throw new Error('PNG exceeds 128 MiB');
  const raw =
    typeof input?.arrayBuffer === 'function'
      ? await input.arrayBuffer()
      : input;
  const bytes =
    raw instanceof Uint8Array
      ? raw
      : raw instanceof ArrayBuffer
        ? new Uint8Array(raw)
        : null;
  if (!bytes)
    throw new Error('Pass a PNG File, Blob, ArrayBuffer or Uint8Array');
  const matches = chunks(bytes).filter(
    (part) => part.type === 'iTXt' && keyword(part.data) === KEY
  );
  if (matches.length !== 1)
    throw new Error(
      matches.length
        ? 'PNG contains conflicting Celldega records'
        : 'PNG has no Celldega saved-view metadata'
    );
  const { data } = matches[0];
  let offset = KEY.length + 1;
  const compressed = data[offset++];
  const method = data[offset++];
  if (![0, 1].includes(compressed) || method !== 0)
    throw new Error('Unsupported PNG text compression');
  for (let i = 0; i < 2; i++) {
    const end = data.indexOf(0, offset);
    if (end < 0) throw new Error('Malformed PNG text metadata');
    offset = end + 1;
  }
  let text = data.subarray(offset);
  if (text.length > MAX_METADATA_BYTES)
    throw new Error('PNG metadata exceeds 64 MiB');
  if (compressed) text = await bounded_inflate(text);
  return validate_png_record(JSON.parse(decoder.decode(text)));
};

/** Attach a complete metadata record without re-encoding the rendered pixels. */
export const write_png = (png, record) => {
  validate_png_record(record);
  const bytes =
    typeof png === 'string'
      ? Uint8Array.from(
          atob(png.replace(/^data:image\/png;base64,/, '')),
          (char) => char.charCodeAt(0)
        )
      : png;
  const metadata = encoder.encode(JSON.stringify(record));
  if (metadata.length > MAX_METADATA_BYTES)
    throw new Error('PNG metadata exceeds 64 MiB');
  // Uncompressed UTF-8 iTXt is portable, requires no compression dependency,
  // and is read by the same Pillow path as Python's compressed iTXt output.
  const saved = chunk(
    'iTXt',
    join([encoder.encode(`${KEY}\0\0\0\0\0`), metadata])
  );
  const parts = chunks(bytes).filter(
    (part) =>
      !(
        ['iTXt', 'tEXt', 'zTXt'].includes(part.type) &&
        keyword(part.data) === KEY
      )
  );
  const end = parts.pop();
  const output = join([
    PNG_SIGNATURE,
    ...parts.map((part) => part.raw),
    saved,
    end.raw,
  ]);
  if (output.length > MAX_PNG_BYTES) throw new Error('PNG exceeds 128 MiB');
  return output;
};

/**
 * A screenshot: a PNG of a saved view's image with the saved view (minus its pixels)
 * embedded, in the same record Python's `screenshot()` writes.
 * @param {object} snapshot - A saved view from `await viz.snapshot()`.
 * @param {{title?: string}} [options]
 * @returns {Blob} An `image/png` Blob.
 */
export const screenshot_png = (snapshot, { title = '' } = {}) => {
  if (!snapshot?.image?.png) throw new Error('Saved view has no PNG image');
  const { image, observed_state, ...compact } = snapshot;
  const record = {
    celldega_screenshot: 3,
    title,
    description: snapshot.description || '',
    author: snapshot.author || '',
    created: snapshot.captured_at,
    celldega: snapshot.renderer?.version || '',
    restoration: snapshot.restoration,
    size: [image.width, image.height],
    widgets: [
      { source: snapshot.source || {}, observed_state, snapshot: compact },
    ],
    metadata: {},
  };
  return new Blob([write_png(image.png, record)], { type: 'image/png' });
};
