
let wasm;

const cachedTextDecoder = new TextDecoder('utf-8', { ignoreBOM: true, fatal: true });

cachedTextDecoder.decode();

let cachedUint8Memory0 = new Uint8Array();

function getUint8Memory0() {
    if (cachedUint8Memory0.byteLength === 0) {
        cachedUint8Memory0 = new Uint8Array(wasm.memory.buffer);
    }
    return cachedUint8Memory0;
}

function getStringFromWasm0(ptr, len) {
    return cachedTextDecoder.decode(getUint8Memory0().subarray(ptr, ptr + len));
}

const heap = new Array(32).fill(undefined);

heap.push(undefined, null, true, false);

let heap_next = heap.length;

function addHeapObject(obj) {
    if (heap_next === heap.length) heap.push(heap.length + 1);
    const idx = heap_next;
    heap_next = heap[idx];

    heap[idx] = obj;
    return idx;
}

function getObject(idx) { return heap[idx]; }

function dropObject(idx) {
    if (idx < 36) return;
    heap[idx] = heap_next;
    heap_next = idx;
}

function takeObject(idx) {
    const ret = getObject(idx);
    dropObject(idx);
    return ret;
}

function debugString(val) {
    // primitive types
    const type = typeof val;
    if (type == 'number' || type == 'boolean' || val == null) {
        return  `${val}`;
    }
    if (type == 'string') {
        return `"${val}"`;
    }
    if (type == 'symbol') {
        const description = val.description;
        if (description == null) {
            return 'Symbol';
        } else {
            return `Symbol(${description})`;
        }
    }
    if (type == 'function') {
        const name = val.name;
        if (typeof name == 'string' && name.length > 0) {
            return `Function(${name})`;
        } else {
            return 'Function';
        }
    }
    // objects
    if (Array.isArray(val)) {
        const length = val.length;
        let debug = '[';
        if (length > 0) {
            debug += debugString(val[0]);
        }
        for(let i = 1; i < length; i++) {
            debug += ', ' + debugString(val[i]);
        }
        debug += ']';
        return debug;
    }
    // Test for built-in
    const builtInMatches = /\[object ([^\]]+)\]/.exec(toString.call(val));
    let className;
    if (builtInMatches.length > 1) {
        className = builtInMatches[1];
    } else {
        // Failed to match the standard '[object ClassName]'
        return toString.call(val);
    }
    if (className == 'Object') {
        // we're a user defined class or Object
        // JSON.stringify avoids problems with cycles, and is generally much
        // easier than looping through ownProperties of `val`.
        try {
            return 'Object(' + JSON.stringify(val) + ')';
        } catch (_) {
            return 'Object';
        }
    }
    // errors
    if (val instanceof Error) {
        return `${val.name}: ${val.message}\n${val.stack}`;
    }
    // TODO we could test for more things here, like `Set`s and `Map`s.
    return className;
}

let WASM_VECTOR_LEN = 0;

const cachedTextEncoder = new TextEncoder('utf-8');

const encodeString = (typeof cachedTextEncoder.encodeInto === 'function'
    ? function (arg, view) {
    return cachedTextEncoder.encodeInto(arg, view);
}
    : function (arg, view) {
    const buf = cachedTextEncoder.encode(arg);
    view.set(buf);
    return {
        read: arg.length,
        written: buf.length
    };
});

function passStringToWasm0(arg, malloc, realloc) {

    if (realloc === undefined) {
        const buf = cachedTextEncoder.encode(arg);
        const ptr = malloc(buf.length);
        getUint8Memory0().subarray(ptr, ptr + buf.length).set(buf);
        WASM_VECTOR_LEN = buf.length;
        return ptr;
    }

    let len = arg.length;
    let ptr = malloc(len);

    const mem = getUint8Memory0();

    let offset = 0;

    for (; offset < len; offset++) {
        const code = arg.charCodeAt(offset);
        if (code > 0x7F) break;
        mem[ptr + offset] = code;
    }

    if (offset !== len) {
        if (offset !== 0) {
            arg = arg.slice(offset);
        }
        ptr = realloc(ptr, len, len = offset + arg.length * 3);
        const view = getUint8Memory0().subarray(ptr + offset, ptr + len);
        const ret = encodeString(arg, view);

        offset += ret.written;
    }

    WASM_VECTOR_LEN = offset;
    return ptr;
}

let cachedInt32Memory0 = new Int32Array();

function getInt32Memory0() {
    if (cachedInt32Memory0.byteLength === 0) {
        cachedInt32Memory0 = new Int32Array(wasm.memory.buffer);
    }
    return cachedInt32Memory0;
}

function makeMutClosure(arg0, arg1, dtor, f) {
    const state = { a: arg0, b: arg1, cnt: 1, dtor };
    const real = (...args) => {
        // First up with a closure we increment the internal reference
        // count. This ensures that the Rust closure environment won't
        // be deallocated while we're invoking it.
        state.cnt++;
        const a = state.a;
        state.a = 0;
        try {
            return f(a, state.b, ...args);
        } finally {
            if (--state.cnt === 0) {
                wasm.__wbindgen_export_2.get(state.dtor)(a, state.b);

            } else {
                state.a = a;
            }
        }
    };
    real.original = state;

    return real;
}
function __wbg_adapter_26(arg0, arg1, arg2) {
    wasm._dyn_core__ops__function__FnMut__A____Output___R_as_wasm_bindgen__closure__WasmClosure___describe__invoke__h3585afe01e623669(arg0, arg1, addHeapObject(arg2));
}

const u32CvtShim = new Uint32Array(2);

const int64CvtShim = new BigInt64Array(u32CvtShim.buffer);

let cachedBigUint64Memory0 = new BigUint64Array();

function getBigUint64Memory0() {
    if (cachedBigUint64Memory0.byteLength === 0) {
        cachedBigUint64Memory0 = new BigUint64Array(wasm.memory.buffer);
    }
    return cachedBigUint64Memory0;
}

function getArrayU64FromWasm0(ptr, len) {
    return getBigUint64Memory0().subarray(ptr / 8, ptr / 8 + len);
}

function passArray8ToWasm0(arg, malloc) {
    const ptr = malloc(arg.length * 1);
    getUint8Memory0().set(arg, ptr / 1);
    WASM_VECTOR_LEN = arg.length;
    return ptr;
}
/**
* Read a Parquet file into Arrow data using the [`arrow2`](https://crates.io/crates/arrow2) and
* [`parquet2`](https://crates.io/crates/parquet2) Rust crates.
*
* Example:
*
* ```js
* import { tableFromIPC } from "apache-arrow";
* // Edit the `parquet-wasm` import as necessary
* import { readParquet } from "parquet-wasm/node2";
*
* const resp = await fetch("https://example.com/file.parquet");
* const parquetUint8Array = new Uint8Array(await resp.arrayBuffer());
* const arrowUint8Array = readParquet(parquetUint8Array);
* const arrowTable = tableFromIPC(arrowUint8Array);
* ```
*
* @param parquet_file Uint8Array containing Parquet data
* @returns Uint8Array containing Arrow data in [IPC Stream format](https://arrow.apache.org/docs/format/Columnar.html#ipc-streaming-format). To parse this into an Arrow table, pass to `tableFromIPC` in the Arrow JS bindings.
* @param {Uint8Array} parquet_file
* @returns {Uint8Array}
*/
export function readParquet(parquet_file) {
    try {
        const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
        const ptr0 = passArray8ToWasm0(parquet_file, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        wasm.readParquet(retptr, ptr0, len0);
        var r0 = getInt32Memory0()[retptr / 4 + 0];
        var r1 = getInt32Memory0()[retptr / 4 + 1];
        var r2 = getInt32Memory0()[retptr / 4 + 2];
        if (r2) {
            throw takeObject(r1);
        }
        return takeObject(r0);
    } finally {
        wasm.__wbindgen_add_to_stack_pointer(16);
    }
}

/**
* Read a Parquet file into Arrow data using the [`arrow2`](https://crates.io/crates/arrow2) and
* [`parquet2`](https://crates.io/crates/parquet2) Rust crates.
*
* Example:
*
* ```js
* import { tableFromIPC } from "apache-arrow";
* // Edit the `parquet-wasm` import as necessary
* import { _readParquetFFI } from "parquet-wasm/node2";
*
* const resp = await fetch("https://example.com/file.parquet");
* const parquetUint8Array = new Uint8Array(await resp.arrayBuffer());
* const wasmArrowTable = _readParquetFFI(parquetUint8Array);
* // Pointer to the ArrowArray FFI struct for the first record batch and first column
* const arrayPtr = wasmArrowTable.array(0, 0);
* ```
*
* @param parquet_file Uint8Array containing Parquet data
* @returns an {@linkcode FFIArrowTable} object containing the parsed Arrow table in WebAssembly memory. To read into an Arrow JS table, you'll need to use the Arrow C Data interface.
* @param {Uint8Array} parquet_file
* @returns {FFIArrowTable}
*/
export function _readParquetFFI(parquet_file) {
    try {
        const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
        const ptr0 = passArray8ToWasm0(parquet_file, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        wasm._readParquetFFI(retptr, ptr0, len0);
        var r0 = getInt32Memory0()[retptr / 4 + 0];
        var r1 = getInt32Memory0()[retptr / 4 + 1];
        var r2 = getInt32Memory0()[retptr / 4 + 2];
        if (r2) {
            throw takeObject(r1);
        }
        return FFIArrowTable.__wrap(r0);
    } finally {
        wasm.__wbindgen_add_to_stack_pointer(16);
    }
}

/**
* Read metadata from a Parquet file using the [`arrow2`](https://crates.io/crates/arrow2) and
* [`parquet2`](https://crates.io/crates/parquet2) Rust crates.
*
* Example:
*
* ```js
* // Edit the `parquet-wasm` import as necessary
* import { readMetadata } from "parquet-wasm/node2";
*
* const resp = await fetch("https://example.com/file.parquet");
* const parquetUint8Array = new Uint8Array(await resp.arrayBuffer());
* const parquetFileMetaData = readMetadata(parquetUint8Array);
* ```
*
* @param parquet_file Uint8Array containing Parquet data
* @returns a {@linkcode FileMetaData} object containing metadata of the Parquet file.
* @param {Uint8Array} parquet_file
* @returns {FileMetaData}
*/
export function readMetadata(parquet_file) {
    try {
        const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
        const ptr0 = passArray8ToWasm0(parquet_file, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        wasm.readMetadata(retptr, ptr0, len0);
        var r0 = getInt32Memory0()[retptr / 4 + 0];
        var r1 = getInt32Memory0()[retptr / 4 + 1];
        var r2 = getInt32Memory0()[retptr / 4 + 2];
        if (r2) {
            throw takeObject(r1);
        }
        return FileMetaData.__wrap(r0);
    } finally {
        wasm.__wbindgen_add_to_stack_pointer(16);
    }
}

function _assertClass(instance, klass) {
    if (!(instance instanceof klass)) {
        throw new Error(`expected instance of ${klass.name}`);
    }
    return instance.ptr;
}
/**
* Read a single row group from a Parquet file into Arrow data using the
* [`arrow2`](https://crates.io/crates/arrow2) and [`parquet2`](https://crates.io/crates/parquet2)
* Rust crates.
*
* Example:
*
* ```js
* import { tableFromIPC } from "apache-arrow";
* // Edit the `parquet-wasm` import as necessary
* import { readRowGroup, readMetadata } from "parquet-wasm/node2";
*
* const resp = await fetch("https://example.com/file.parquet");
* const parquetUint8Array = new Uint8Array(await resp.arrayBuffer());
* const parquetFileMetaData = readMetadata(parquetUint8Array);
*
* // Read only the first row group
* const arrowIpcBuffer = wasm.readRowGroup(parquetUint8Array, parquetFileMetaData, 0);
* const arrowTable = tableFromIPC(arrowUint8Array);
* ```
*
* Note that you can get the number of row groups in a Parquet file using {@linkcode FileMetaData.numRowGroups}
*
* @param parquet_file Uint8Array containing Parquet data
* @param meta {@linkcode FileMetaData} from a call to {@linkcode readMetadata}
* @param i Number index of the row group to parse
* @returns Uint8Array containing Arrow data in [IPC Stream format](https://arrow.apache.org/docs/format/Columnar.html#ipc-streaming-format). To parse this into an Arrow table, pass to `tableFromIPC` in the Arrow JS bindings.
* @param {Uint8Array} parquet_file
* @param {FileMetaData} meta
* @param {number} i
* @returns {Uint8Array}
*/
export function readRowGroup(parquet_file, meta, i) {
    try {
        const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
        const ptr0 = passArray8ToWasm0(parquet_file, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        _assertClass(meta, FileMetaData);
        wasm.readRowGroup(retptr, ptr0, len0, meta.ptr, i);
        var r0 = getInt32Memory0()[retptr / 4 + 0];
        var r1 = getInt32Memory0()[retptr / 4 + 1];
        var r2 = getInt32Memory0()[retptr / 4 + 2];
        if (r2) {
            throw takeObject(r1);
        }
        return takeObject(r0);
    } finally {
        wasm.__wbindgen_add_to_stack_pointer(16);
    }
}

/**
* Asynchronously read metadata from a Parquet file using the
* [`arrow2`](https://crates.io/crates/arrow2) and [`parquet2`](https://crates.io/crates/parquet2)
* Rust crates.
*
* For now, this requires knowing the content length of the file, but hopefully this will be
* relaxed in the future.
*
* Example:
*
* ```js
* // Edit the `parquet-wasm` import as necessary
* import { readMetadataAsync } from "parquet-wasm";
*
* const url = "https://example.com/file.parquet";
* const headResp = await fetch(url, {method: 'HEAD'});
* const length = parseInt(headResp.headers.get('Content-Length'));
*
* const parquetFileMetaData = await readMetadataAsync(url, length);
* ```
*
* @param url String location of remote Parquet file containing Parquet data
* @param content_length Number content length of file in bytes
* @returns a {@linkcode FileMetaData} object containing metadata of the Parquet file.
* @param {string} url
* @param {number} content_length
* @returns {Promise<FileMetaData>}
*/
export function readMetadataAsync(url, content_length) {
    const ptr0 = passStringToWasm0(url, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
    const len0 = WASM_VECTOR_LEN;
    const ret = wasm.readMetadataAsync(ptr0, len0, content_length);
    return takeObject(ret);
}

/**
* Asynchronously read a single row group from a Parquet file into Arrow data using the
* [`arrow2`](https://crates.io/crates/arrow2) and [`parquet2`](https://crates.io/crates/parquet2)
* Rust crates.
*
* Example:
*
* ```js
* import { tableFromIPC } from "apache-arrow";
* // Edit the `parquet-wasm` import as necessary
* import { readRowGroupAsync, readMetadataAsync } from "parquet-wasm";
*
* const url = "https://example.com/file.parquet";
* const headResp = await fetch(url, {method: 'HEAD'});
* const length = parseInt(headResp.headers.get('Content-Length'));
*
* const parquetFileMetaData = await readMetadataAsync(url, length);
*
* // Read all batches from the file in parallel
* const promises = [];
* for (let i = 0; i < parquetFileMetaData.numRowGroups(); i++) {
*   // IMPORTANT: For now, calling `copy()` on the metadata object is required whenever passing in to
*   // a function. Hopefully this can be resolved in the future sometime
*   const rowGroupPromise = wasm.readRowGroupAsync2(url, length, parquetFileMetaData.copy(), i);
*   promises.push(rowGroupPromise);
* }
*
* const recordBatchChunks = await Promise.all(promises);
* const table = new arrow.Table(recordBatchChunks);
* ```
*
* Note that you can get the number of row groups in a Parquet file using {@linkcode FileMetaData.numRowGroups}
*
* @param url String location of remote Parquet file containing Parquet data
* @param content_length Number content length of file in bytes
* @param meta {@linkcode FileMetaData} from a call to {@linkcode readMetadata}
* @param i Number index of the row group to load
* @returns Uint8Array containing Arrow data in [IPC Stream format](https://arrow.apache.org/docs/format/Columnar.html#ipc-streaming-format). To parse this into an Arrow table, pass to `tableFromIPC` in the Arrow JS bindings.
* @param {string} url
* @param {RowGroupMetaData} row_group_meta
* @param {ArrowSchema} arrow_schema
* @returns {Promise<Uint8Array>}
*/
export function readRowGroupAsync(url, row_group_meta, arrow_schema) {
    const ptr0 = passStringToWasm0(url, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
    const len0 = WASM_VECTOR_LEN;
    _assertClass(row_group_meta, RowGroupMetaData);
    var ptr1 = row_group_meta.ptr;
    row_group_meta.ptr = 0;
    _assertClass(arrow_schema, ArrowSchema);
    var ptr2 = arrow_schema.ptr;
    arrow_schema.ptr = 0;
    const ret = wasm.readRowGroupAsync(ptr0, len0, ptr1, ptr2);
    return takeObject(ret);
}

function isLikeNone(x) {
    return x === undefined || x === null;
}
/**
* Write Arrow data to a Parquet file using the [`arrow2`](https://crates.io/crates/arrow2) and
* [`parquet2`](https://crates.io/crates/parquet2) Rust crates.
*
* For example, to create a Parquet file with Snappy compression:
*
* ```js
* import { tableToIPC } from "apache-arrow";
* // Edit the `parquet-wasm` import as necessary
* import { WriterPropertiesBuilder, Compression, writeParquet } from "parquet-wasm/node2";
*
* // Given an existing arrow table under `table`
* const arrowUint8Array = tableToIPC(table, "file");
* const writerProperties = new WriterPropertiesBuilder()
*   .setCompression(Compression.SNAPPY)
*   .build();
* const parquetUint8Array = writeParquet(arrowUint8Array, writerProperties);
* ```
*
* If `writerProperties` is not provided or is `null`, the default writer properties will be used.
* This is equivalent to `new WriterPropertiesBuilder().build()`.
*
* @param arrow_file Uint8Array containing Arrow data in [IPC **File** format](https://arrow.apache.org/docs/format/Columnar.html#ipc-file-format). If you have an Arrow table in JS, call `tableToIPC(table, "file")` in the JS bindings and pass the result here.
* @param writer_properties Configuration for writing to Parquet. Use the {@linkcode WriterPropertiesBuilder} to build a writing configuration, then call `.build()` to create an immutable writer properties to pass in here.
* @returns Uint8Array containing written Parquet data.
* @param {Uint8Array} arrow_file
* @param {WriterProperties | undefined} writer_properties
* @returns {Uint8Array}
*/
export function writeParquet(arrow_file, writer_properties) {
    try {
        const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
        const ptr0 = passArray8ToWasm0(arrow_file, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        let ptr1 = 0;
        if (!isLikeNone(writer_properties)) {
            _assertClass(writer_properties, WriterProperties);
            ptr1 = writer_properties.ptr;
            writer_properties.ptr = 0;
        }
        wasm.writeParquet(retptr, ptr0, len0, ptr1);
        var r0 = getInt32Memory0()[retptr / 4 + 0];
        var r1 = getInt32Memory0()[retptr / 4 + 1];
        var r2 = getInt32Memory0()[retptr / 4 + 2];
        if (r2) {
            throw takeObject(r1);
        }
        return takeObject(r0);
    } finally {
        wasm.__wbindgen_add_to_stack_pointer(16);
    }
}

/**
* Write Arrow data to a Parquet file using the [`arrow2`](https://crates.io/crates/arrow2) and
* [`parquet2`](https://crates.io/crates/parquet2) Rust crates.
*
* For example, to create a Parquet file with Snappy compression:
*
* ```js
* import { tableToIPC } from "apache-arrow";
* // Edit the `parquet-wasm` import as necessary
* import { WriterPropertiesBuilder, Compression, _writeParquetFFI } from "parquet-wasm/node2";
*
* // Given an existing arrow table under `table`
* const arrowUint8Array = tableToIPC(table, "file");
* const writerProperties = new WriterPropertiesBuilder()
*   .setCompression(Compression.SNAPPY)
*   .build();
* const parquetUint8Array = writeParquet(arrowUint8Array, writerProperties);
* ```
*
* If `writerProperties` is not provided or is `null`, the default writer properties will be used.
* This is equivalent to `new WriterPropertiesBuilder().build()`.
*
* @param arrow_table {@linkcode FFIArrowTable} Arrow Table in Wasm memory
* @param writer_properties Configuration for writing to Parquet. Use the {@linkcode WriterPropertiesBuilder} to build a writing configuration, then call `.build()` to create an immutable writer properties to pass in here.
* @returns Uint8Array containing written Parquet data.
* @param {FFIArrowTable} arrow_table
* @param {WriterProperties | undefined} writer_properties
* @returns {Uint8Array}
*/
export function _writeParquetFFI(arrow_table, writer_properties) {
    try {
        const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
        _assertClass(arrow_table, FFIArrowTable);
        var ptr0 = arrow_table.ptr;
        arrow_table.ptr = 0;
        let ptr1 = 0;
        if (!isLikeNone(writer_properties)) {
            _assertClass(writer_properties, WriterProperties);
            ptr1 = writer_properties.ptr;
            writer_properties.ptr = 0;
        }
        wasm._writeParquetFFI(retptr, ptr0, ptr1);
        var r0 = getInt32Memory0()[retptr / 4 + 0];
        var r1 = getInt32Memory0()[retptr / 4 + 1];
        var r2 = getInt32Memory0()[retptr / 4 + 2];
        if (r2) {
            throw takeObject(r1);
        }
        return takeObject(r0);
    } finally {
        wasm.__wbindgen_add_to_stack_pointer(16);
    }
}

function handleError(f, args) {
    try {
        return f.apply(this, args);
    } catch (e) {
        wasm.__wbindgen_exn_store(addHeapObject(e));
    }
}
function __wbg_adapter_127(arg0, arg1, arg2, arg3) {
    wasm.wasm_bindgen__convert__closures__invoke2_mut__haace1f71440c779f(arg0, arg1, addHeapObject(arg2), addHeapObject(arg3));
}

/**
* Supported compression algorithms.
*
* Codecs added in format version X.Y can be read by readers based on X.Y and later.
* Codec support may vary between readers based on the format version and
* libraries available at runtime.
*/
export const Compression = Object.freeze({ UNCOMPRESSED:0,"0":"UNCOMPRESSED",SNAPPY:1,"1":"SNAPPY",GZIP:2,"2":"GZIP",BROTLI:3,"3":"BROTLI",
/**
* @deprecated as of Parquet 2.9.0.
* Switch to LZ4_RAW
*/
LZ4:4,"4":"LZ4",ZSTD:5,"5":"ZSTD",LZ4_RAW:6,"6":"LZ4_RAW", });
/**
* Encodings supported by Parquet.
* Not all encodings are valid for all types. These enums are also used to specify the
* encoding of definition and repetition levels.
*/
export const Encoding = Object.freeze({
/**
* Default byte encoding.
* - BOOLEAN - 1 bit per value, 0 is false; 1 is true.
* - INT32 - 4 bytes per value, stored as little-endian.
* - INT64 - 8 bytes per value, stored as little-endian.
* - FLOAT - 4 bytes per value, stored as little-endian.
* - DOUBLE - 8 bytes per value, stored as little-endian.
* - BYTE_ARRAY - 4 byte length stored as little endian, followed by bytes.
* - FIXED_LEN_BYTE_ARRAY - just the bytes are stored.
*/
PLAIN:0,"0":"PLAIN",
/**
* **Deprecated** dictionary encoding.
*
* The values in the dictionary are encoded using PLAIN encoding.
* Since it is deprecated, RLE_DICTIONARY encoding is used for a data page, and
* PLAIN encoding is used for dictionary page.
*/
PLAIN_DICTIONARY:1,"1":"PLAIN_DICTIONARY",
/**
* Group packed run length encoding.
*
* Usable for definition/repetition levels encoding and boolean values.
*/
RLE:2,"2":"RLE",
/**
* Bit packed encoding.
*
* This can only be used if the data has a known max width.
* Usable for definition/repetition levels encoding.
*/
BIT_PACKED:3,"3":"BIT_PACKED",
/**
* Delta encoding for integers, either INT32 or INT64.
*
* Works best on sorted data.
*/
DELTA_BINARY_PACKED:4,"4":"DELTA_BINARY_PACKED",
/**
* Encoding for byte arrays to separate the length values and the data.
*
* The lengths are encoded using DELTA_BINARY_PACKED encoding.
*/
DELTA_LENGTH_BYTE_ARRAY:5,"5":"DELTA_LENGTH_BYTE_ARRAY",
/**
* Incremental encoding for byte arrays.
*
* Prefix lengths are encoded using DELTA_BINARY_PACKED encoding.
* Suffixes are stored using DELTA_LENGTH_BYTE_ARRAY encoding.
*/
DELTA_BYTE_ARRAY:6,"6":"DELTA_BYTE_ARRAY",
/**
* Dictionary encoding.
*
* The ids are encoded using the RLE encoding.
*/
RLE_DICTIONARY:7,"7":"RLE_DICTIONARY",
/**
* Encoding for floating-point data.
*
* K byte-streams are created where K is the size in bytes of the data type.
* The individual bytes of an FP value are scattered to the corresponding stream and
* the streams are concatenated.
* This itself does not reduce the size of the data but can lead to better compression
* afterwards.
*/
BYTE_STREAM_SPLIT:8,"8":"BYTE_STREAM_SPLIT", });
/**
* The Parquet version to use when writing
*/
export const WriterVersion = Object.freeze({ V1:0,"0":"V1",V2:1,"1":"V2", });
/**
* Metadata for a Parquet file.
*/
export class ArrowSchema {

    static __wrap(ptr) {
        const obj = Object.create(ArrowSchema.prototype);
        obj.ptr = ptr;

        return obj;
    }

    __destroy_into_raw() {
        const ptr = this.ptr;
        this.ptr = 0;

        return ptr;
    }

    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_arrowschema_free(ptr);
    }
    /**
    * Clone this struct in wasm memory.
    * @returns {ArrowSchema}
    */
    copy() {
        const ret = wasm.arrowschema_copy(this.ptr);
        return ArrowSchema.__wrap(ret);
    }
}
/**
* Metadata for a column chunk.
*/
export class ColumnChunkMetaData {

    static __wrap(ptr) {
        const obj = Object.create(ColumnChunkMetaData.prototype);
        obj.ptr = ptr;

        return obj;
    }

    __destroy_into_raw() {
        const ptr = this.ptr;
        this.ptr = 0;

        return ptr;
    }

    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_columnchunkmetadata_free(ptr);
    }
    /**
    * File where the column chunk is stored.
    *
    * If not set, assumed to belong to the same file as the metadata.
    * This path is relative to the current file.
    * @returns {string | undefined}
    */
    filePath() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.columnchunkmetadata_filePath(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            let v0;
            if (r0 !== 0) {
                v0 = getStringFromWasm0(r0, r1).slice();
                wasm.__wbindgen_free(r0, r1 * 1);
            }
            return v0;
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
        }
    }
    /**
    * Byte offset in `file_path()`.
    * @returns {bigint}
    */
    fileOffset() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.columnchunkmetadata_fileOffset(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            u32CvtShim[0] = r0;
            u32CvtShim[1] = r1;
            const n0 = int64CvtShim[0];
            return n0;
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
        }
    }
    /**
    * @returns {string}
    */
    pathInSchema() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.columnchunkmetadata_pathInSchema(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            return getStringFromWasm0(r0, r1);
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
            wasm.__wbindgen_free(r0, r1);
        }
    }
    /**
    * @returns {boolean}
    */
    statistics_exist() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.columnchunkmetadata_statistics_exist(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            var r2 = getInt32Memory0()[retptr / 4 + 2];
            if (r2) {
                throw takeObject(r1);
            }
            return r0 !== 0;
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
        }
    }
    /**
    * @returns {any}
    */
    getStatisticsMinValue() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.columnchunkmetadata_getStatisticsMinValue(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            var r2 = getInt32Memory0()[retptr / 4 + 2];
            if (r2) {
                throw takeObject(r1);
            }
            return takeObject(r0);
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
        }
    }
    /**
    * @returns {any}
    */
    getStatisticsMaxValue() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.columnchunkmetadata_getStatisticsMaxValue(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            var r2 = getInt32Memory0()[retptr / 4 + 2];
            if (r2) {
                throw takeObject(r1);
            }
            return takeObject(r0);
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
        }
    }
    /**
    * @returns {any}
    */
    getStatisticsNullCount() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.columnchunkmetadata_getStatisticsNullCount(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            var r2 = getInt32Memory0()[retptr / 4 + 2];
            if (r2) {
                throw takeObject(r1);
            }
            return takeObject(r0);
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
        }
    }
    /**
    * Total number of values in this column chunk. Note that this is not necessarily the number
    * of rows. E.g. the (nested) array `[[1, 2], [3]]` has 2 rows and 3 values.
    * @returns {bigint}
    */
    numValues() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.columnchunkmetadata_numValues(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            u32CvtShim[0] = r0;
            u32CvtShim[1] = r1;
            const n0 = int64CvtShim[0];
            return n0;
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
        }
    }
    /**
    * Returns the total compressed data size of this column chunk.
    * @returns {bigint}
    */
    compressedSize() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.columnchunkmetadata_compressedSize(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            u32CvtShim[0] = r0;
            u32CvtShim[1] = r1;
            const n0 = int64CvtShim[0];
            return n0;
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
        }
    }
    /**
    * Returns the total uncompressed data size of this column chunk.
    * @returns {bigint}
    */
    uncompressedSize() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.columnchunkmetadata_uncompressedSize(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            u32CvtShim[0] = r0;
            u32CvtShim[1] = r1;
            const n0 = int64CvtShim[0];
            return n0;
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
        }
    }
    /**
    * Returns the offset for the column data.
    * @returns {bigint}
    */
    dataPageOffset() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.columnchunkmetadata_dataPageOffset(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            u32CvtShim[0] = r0;
            u32CvtShim[1] = r1;
            const n0 = int64CvtShim[0];
            return n0;
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
        }
    }
    /**
    * Returns `true` if this column chunk contains a index page, `false` otherwise.
    * @returns {boolean}
    */
    hasIndexPage() {
        const ret = wasm.columnchunkmetadata_hasIndexPage(this.ptr);
        return ret !== 0;
    }
    /**
    * Returns the offset for the index page.
    * @returns {bigint | undefined}
    */
    indexPageOffset() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.columnchunkmetadata_indexPageOffset(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            var r2 = getInt32Memory0()[retptr / 4 + 2];
            u32CvtShim[0] = r1;
            u32CvtShim[1] = r2;
            const n0 = r0 === 0 ? undefined : int64CvtShim[0];
            return n0;
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
        }
    }
    /**
    * Returns the offset for the dictionary page, if any.
    * @returns {bigint | undefined}
    */
    dictionaryPageOffset() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.columnchunkmetadata_dictionaryPageOffset(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            var r2 = getInt32Memory0()[retptr / 4 + 2];
            u32CvtShim[0] = r1;
            u32CvtShim[1] = r2;
            const n0 = r0 === 0 ? undefined : int64CvtShim[0];
            return n0;
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
        }
    }
    /**
    * Returns the number of encodings for this column
    * @returns {number}
    */
    numColumnEncodings() {
        const ret = wasm.columnchunkmetadata_numColumnEncodings(this.ptr);
        return ret >>> 0;
    }
    /**
    * Returns the offset and length in bytes of the column chunk within the file
    * @returns {BigUint64Array}
    */
    byteRange() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.columnchunkmetadata_byteRange(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            var v0 = getArrayU64FromWasm0(r0, r1).slice();
            wasm.__wbindgen_free(r0, r1 * 8);
            return v0;
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
        }
    }
}
/**
* Wrapper around an ArrowArray FFI struct in Wasm memory.
*/
export class FFIArrowArray {

    __destroy_into_raw() {
        const ptr = this.ptr;
        this.ptr = 0;

        return ptr;
    }

    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_ffiarrowarray_free(ptr);
    }
    /**
    * @returns {number}
    */
    addr() {
        const ret = wasm.ffiarrowarray_addr(this.ptr);
        return ret;
    }
    /**
    */
    // commented out becuase of 
    // [WARNING] Duplicate member "free" in class body [duplicate-class-member]
    // free() {
    //     const ptr = this.__destroy_into_raw();
    //     wasm.ffiarrowarray_free(ptr);
    // }
    /**
    */
    drop() {
        const ptr = this.__destroy_into_raw();
        wasm.ffiarrowarray_drop(ptr);
    }
}
/**
* Wrapper to represent an Arrow Chunk in Wasm memory, e.g. a  collection of FFI ArrowArray
* structs
*/
export class FFIArrowChunk {

    __destroy_into_raw() {
        const ptr = this.ptr;
        this.ptr = 0;

        return ptr;
    }

    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_ffiarrowchunk_free(ptr);
    }
    /**
    * @returns {number}
    */
    length() {
        const ret = wasm.ffiarrowchunk_length(this.ptr);
        return ret >>> 0;
    }
    /**
    * @param {number} i
    * @returns {number}
    */
    addr(i) {
        const ret = wasm.ffiarrowchunk_addr(this.ptr, i);
        return ret;
    }
}
/**
* Wrapper around an ArrowSchema FFI struct in Wasm memory.
*/
export class FFIArrowField {

    __destroy_into_raw() {
        const ptr = this.ptr;
        this.ptr = 0;

        return ptr;
    }

    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_ffiarrowfield_free(ptr);
    }
    /**
    * @returns {number}
    */
    addr() {
        const ret = wasm.ffiarrowfield_addr(this.ptr);
        return ret;
    }
}
/**
* Wrapper around a collection of FFI ArrowSchema structs in Wasm memory
*/
export class FFIArrowSchema {

    __destroy_into_raw() {
        const ptr = this.ptr;
        this.ptr = 0;

        return ptr;
    }

    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_ffiarrowschema_free(ptr);
    }
    /**
    * @returns {number}
    */
    length() {
        const ret = wasm.ffiarrowschema_length(this.ptr);
        return ret >>> 0;
    }
    /**
    * @param {number} i
    * @returns {number}
    */
    addr(i) {
        const ret = wasm.ffiarrowschema_addr(this.ptr, i);
        return ret;
    }
}
/**
* Wrapper around an Arrow Table in Wasm memory (a lisjst of FFI ArrowSchema structs plus a list of
* lists of ArrowArray FFI structs.)
*/
export class FFIArrowTable {

    static __wrap(ptr) {
        const obj = Object.create(FFIArrowTable.prototype);
        obj.ptr = ptr;

        return obj;
    }

    __destroy_into_raw() {
        const ptr = this.ptr;
        this.ptr = 0;

        return ptr;
    }

    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_ffiarrowtable_free(ptr);
    }
    /**
    * Get the number of Fields in the table schema
    * @returns {number}
    */
    schemaLength() {
        const ret = wasm.ffiarrowtable_schemaLength(this.ptr);
        return ret >>> 0;
    }
    /**
    * Get the pointer to one ArrowSchema FFI struct
    * @param i number the index of the field in the schema to use
    * @param {number} i
    * @returns {number}
    */
    schemaAddr(i) {
        const ret = wasm.ffiarrowtable_schemaAddr(this.ptr, i);
        return ret;
    }
    /**
    * Get the total number of chunks in the table
    * @returns {number}
    */
    chunksLength() {
        const ret = wasm.ffiarrowtable_chunksLength(this.ptr);
        return ret >>> 0;
    }
    /**
    * Get the number of columns in a given chunk
    * @param {number} i
    * @returns {number}
    */
    chunkLength(i) {
        const ret = wasm.ffiarrowtable_chunkLength(this.ptr, i);
        return ret >>> 0;
    }
    /**
    * Get the pointer to one ArrowArray FFI struct for a given chunk index and column index
    * @param chunk number The chunk index to use
    * @param column number The column index to use
    * @returns number pointer to an ArrowArray FFI struct in Wasm memory
    * @param {number} chunk
    * @param {number} column
    * @returns {number}
    */
    arrayAddr(chunk, column) {
        const ret = wasm.ffiarrowtable_arrayAddr(this.ptr, chunk, column);
        return ret;
    }
    /**
    */
    drop() {
        const ptr = this.__destroy_into_raw();
        wasm.ffiarrowtable_drop(ptr);
    }
}
/**
* Metadata for a Parquet file.
*/
export class FileMetaData {

    static __wrap(ptr) {
        const obj = Object.create(FileMetaData.prototype);
        obj.ptr = ptr;

        return obj;
    }

    __destroy_into_raw() {
        const ptr = this.ptr;
        this.ptr = 0;

        return ptr;
    }

    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_filemetadata_free(ptr);
    }
    /**
    * Clone this struct in wasm memory.
    * @returns {FileMetaData}
    */
    copy() {
        const ret = wasm.filemetadata_copy(this.ptr);
        return FileMetaData.__wrap(ret);
    }
    /**
    * Version of this file.
    * @returns {number}
    */
    version() {
        const ret = wasm.filemetadata_version(this.ptr);
        return ret;
    }
    /**
    * number of rows in the file.
    * @returns {number}
    */
    numRows() {
        const ret = wasm.filemetadata_numRows(this.ptr);
        return ret >>> 0;
    }
    /**
    * String message for application that wrote this file.
    * @returns {string | undefined}
    */
    createdBy() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.filemetadata_createdBy(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            let v0;
            if (r0 !== 0) {
                v0 = getStringFromWasm0(r0, r1).slice();
                wasm.__wbindgen_free(r0, r1 * 1);
            }
            return v0;
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
        }
    }
    /**
    * Number of row groups in the file
    * @returns {number}
    */
    numRowGroups() {
        const ret = wasm.filemetadata_numRowGroups(this.ptr);
        return ret >>> 0;
    }
    /**
    * Returns a single RowGroupMetaData by index
    * @param {number} i
    * @returns {RowGroupMetaData}
    */
    rowGroup(i) {
        const ret = wasm.filemetadata_rowGroup(this.ptr, i);
        return RowGroupMetaData.__wrap(ret);
    }
    /**
    * @returns {SchemaDescriptor}
    */
    schema() {
        const ret = wasm.filemetadata_schema(this.ptr);
        return SchemaDescriptor.__wrap(ret);
    }
    /**
    * @returns {any}
    */
    keyValueMetadata() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.filemetadata_keyValueMetadata(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            var r2 = getInt32Memory0()[retptr / 4 + 2];
            if (r2) {
                throw takeObject(r1);
            }
            return takeObject(r0);
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
        }
    }
    /**
    * @returns {ArrowSchema}
    */
    arrowSchema() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.filemetadata_arrowSchema(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            var r2 = getInt32Memory0()[retptr / 4 + 2];
            if (r2) {
                throw takeObject(r1);
            }
            return ArrowSchema.__wrap(r0);
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
        }
    }
}
/**
* Metadata for a row group.
*/
export class RowGroupMetaData {

    static __wrap(ptr) {
        const obj = Object.create(RowGroupMetaData.prototype);
        obj.ptr = ptr;

        return obj;
    }

    __destroy_into_raw() {
        const ptr = this.ptr;
        this.ptr = 0;

        return ptr;
    }

    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_rowgroupmetadata_free(ptr);
    }
    /**
    * Number of rows in this row group.
    * @returns {number}
    */
    numRows() {
        const ret = wasm.rowgroupmetadata_numRows(this.ptr);
        return ret >>> 0;
    }
    /**
    * Number of columns in this row group.
    * @returns {number}
    */
    numColumns() {
        const ret = wasm.rowgroupmetadata_numColumns(this.ptr);
        return ret >>> 0;
    }
    /**
    * Returns a single column chunk metadata by index
    * @param {number} i
    * @returns {ColumnChunkMetaData}
    */
    column(i) {
        const ret = wasm.rowgroupmetadata_column(this.ptr, i);
        return ColumnChunkMetaData.__wrap(ret);
    }
    /**
    * Total byte size of all uncompressed column data in this row group.
    * @returns {number}
    */
    totalByteSize() {
        const ret = wasm.rowgroupmetadata_totalByteSize(this.ptr);
        return ret >>> 0;
    }
    /**
    * Total size of all compressed column data in this row group.
    * @returns {number}
    */
    compressedSize() {
        const ret = wasm.rowgroupmetadata_compressedSize(this.ptr);
        return ret >>> 0;
    }
}
/**
* A schema descriptor. This encapsulates the top-level schemas for all the columns,
* as well as all descriptors for all the primitive columns.
*/
export class SchemaDescriptor {

    static __wrap(ptr) {
        const obj = Object.create(SchemaDescriptor.prototype);
        obj.ptr = ptr;

        return obj;
    }

    __destroy_into_raw() {
        const ptr = this.ptr;
        this.ptr = 0;

        return ptr;
    }

    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_schemadescriptor_free(ptr);
    }
    /**
    * The schemas' name.
    * @returns {string}
    */
    name() {
        try {
            const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
            wasm.schemadescriptor_name(retptr, this.ptr);
            var r0 = getInt32Memory0()[retptr / 4 + 0];
            var r1 = getInt32Memory0()[retptr / 4 + 1];
            return getStringFromWasm0(r0, r1);
        } finally {
            wasm.__wbindgen_add_to_stack_pointer(16);
            wasm.__wbindgen_free(r0, r1);
        }
    }
    /**
    * The number of columns in the schema
    * @returns {number}
    */
    numColumns() {
        const ret = wasm.schemadescriptor_numColumns(this.ptr);
        return ret >>> 0;
    }
    /**
    * The number of fields in the schema
    * @returns {number}
    */
    numFields() {
        const ret = wasm.schemadescriptor_numFields(this.ptr);
        return ret >>> 0;
    }
}
/**
* Immutable struct to hold writing configuration for `writeParquet2`.
*
* Use {@linkcode WriterPropertiesBuilder} to create a configuration, then call {@linkcode
* WriterPropertiesBuilder.build} to create an instance of `WriterProperties`.
*/
export class WriterProperties {

    static __wrap(ptr) {
        const obj = Object.create(WriterProperties.prototype);
        obj.ptr = ptr;

        return obj;
    }

    __destroy_into_raw() {
        const ptr = this.ptr;
        this.ptr = 0;

        return ptr;
    }

    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_writerproperties_free(ptr);
    }
}
/**
* Builder to create a writing configuration for `writeParquet2`
*
* Call {@linkcode build} on the finished builder to create an immputable {@linkcode WriterProperties} to pass to `writeParquet2`
*/
export class WriterPropertiesBuilder {

    static __wrap(ptr) {
        const obj = Object.create(WriterPropertiesBuilder.prototype);
        obj.ptr = ptr;

        return obj;
    }

    __destroy_into_raw() {
        const ptr = this.ptr;
        this.ptr = 0;

        return ptr;
    }

    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_writerpropertiesbuilder_free(ptr);
    }
    /**
    * Returns default state of the builder.
    */
    constructor() {
        const ret = wasm.writerpropertiesbuilder_new();
        return WriterPropertiesBuilder.__wrap(ret);
    }
    /**
    * Finalizes the configuration and returns immutable writer properties struct.
    * @returns {WriterProperties}
    */
    build() {
        const ptr = this.__destroy_into_raw();
        const ret = wasm.writerpropertiesbuilder_build(ptr);
        return WriterProperties.__wrap(ret);
    }
    /**
    * Sets writer version.
    * @param {number} value
    * @returns {WriterPropertiesBuilder}
    */
    setWriterVersion(value) {
        const ptr = this.__destroy_into_raw();
        const ret = wasm.writerpropertiesbuilder_setWriterVersion(ptr, value);
        return WriterPropertiesBuilder.__wrap(ret);
    }
    /**
    * Sets encoding for any column.
    *
    * If dictionary is not enabled, this is treated as a primary encoding for all
    * columns. In case when dictionary is enabled for any column, this value is
    * considered to be a fallback encoding for that column.
    *
    * Panics if user tries to set dictionary encoding here, regardless of dictionary
    * encoding flag being set.
    * @param {number} value
    * @returns {WriterPropertiesBuilder}
    */
    setEncoding(value) {
        const ptr = this.__destroy_into_raw();
        const ret = wasm.writerpropertiesbuilder_setEncoding(ptr, value);
        return WriterPropertiesBuilder.__wrap(ret);
    }
    /**
    * Sets compression codec for any column.
    * @param {number} value
    * @returns {WriterPropertiesBuilder}
    */
    setCompression(value) {
        const ptr = this.__destroy_into_raw();
        const ret = wasm.writerpropertiesbuilder_setCompression(ptr, value);
        return WriterPropertiesBuilder.__wrap(ret);
    }
    /**
    * Sets flag to enable/disable statistics for any column.
    * @param {boolean} value
    * @returns {WriterPropertiesBuilder}
    */
    setStatisticsEnabled(value) {
        const ptr = this.__destroy_into_raw();
        const ret = wasm.writerpropertiesbuilder_setStatisticsEnabled(ptr, value);
        return WriterPropertiesBuilder.__wrap(ret);
    }
}

async function load(module, imports) {
    if (typeof Response === 'function' && module instanceof Response) {
        if (typeof WebAssembly.instantiateStreaming === 'function') {
            try {
                return await WebAssembly.instantiateStreaming(module, imports);

            } catch (e) {
                if (module.headers.get('Content-Type') != 'application/wasm') {
                    console.warn("`WebAssembly.instantiateStreaming` failed because your server does not serve wasm with `application/wasm` MIME type. Falling back to `WebAssembly.instantiate` which is slower. Original error:\n", e);

                } else {
                    throw e;
                }
            }
        }

        const bytes = await module.arrayBuffer();
        return await WebAssembly.instantiate(bytes, imports);

    } else {
        const instance = await WebAssembly.instantiate(module, imports);

        if (instance instanceof WebAssembly.Instance) {
            return { instance, module };

        } else {
            return instance;
        }
    }
}

function getImports() {
    const imports = {};
    imports.wbg = {};
    imports.wbg.__wbg_filemetadata_new = function(arg0) {
        const ret = FileMetaData.__wrap(arg0);
        return addHeapObject(ret);
    };
    imports.wbg.__wbindgen_string_new = function(arg0, arg1) {
        const ret = getStringFromWasm0(arg0, arg1);
        return addHeapObject(ret);
    };
    imports.wbg.__wbindgen_object_drop_ref = function(arg0) {
        takeObject(arg0);
    };
    imports.wbg.__wbindgen_error_new = function(arg0, arg1) {
        const ret = new Error(getStringFromWasm0(arg0, arg1));
        return addHeapObject(ret);
    };
    imports.wbg.__wbindgen_bigint_new = function(arg0, arg1) {
        const ret = BigInt(getStringFromWasm0(arg0, arg1));
        return addHeapObject(ret);
    };
    imports.wbg.__wbindgen_number_new = function(arg0) {
        const ret = arg0;
        return addHeapObject(ret);
    };
    imports.wbg.__wbindgen_object_clone_ref = function(arg0) {
        const ret = getObject(arg0);
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_String_7462bcc0fcdbaf7d = function(arg0, arg1) {
        const ret = String(getObject(arg1));
        const ptr0 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        getInt32Memory0()[arg0 / 4 + 1] = len0;
        getInt32Memory0()[arg0 / 4 + 0] = ptr0;
    };
    imports.wbg.__wbg_set_e93b31d47b90bff6 = function(arg0, arg1, arg2) {
        getObject(arg0)[takeObject(arg1)] = takeObject(arg2);
    };
    imports.wbg.__wbindgen_cb_drop = function(arg0) {
        const obj = takeObject(arg0).original;
        if (obj.cnt-- == 1) {
            obj.a = 0;
            return true;
        }
        const ret = false;
        return ret;
    };
    imports.wbg.__wbg_get_aab8f8a9b87125ad = function() { return handleError(function (arg0, arg1, arg2, arg3) {
        const ret = getObject(arg1).get(getStringFromWasm0(arg2, arg3));
        var ptr0 = isLikeNone(ret) ? 0 : passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        var len0 = WASM_VECTOR_LEN;
        getInt32Memory0()[arg0 / 4 + 1] = len0;
        getInt32Memory0()[arg0 / 4 + 0] = ptr0;
    }, arguments) };
    imports.wbg.__wbg_set_b5c36262f65fae92 = function() { return handleError(function (arg0, arg1, arg2, arg3, arg4) {
        getObject(arg0).set(getStringFromWasm0(arg1, arg2), getStringFromWasm0(arg3, arg4));
    }, arguments) };
    imports.wbg.__wbg_instanceof_Response_240e67e5796c3c6b = function(arg0) {
        const ret = getObject(arg0) instanceof Response;
        return ret;
    };
    imports.wbg.__wbg_headers_aa309e800cf75016 = function(arg0) {
        const ret = getObject(arg0).headers;
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_arrayBuffer_ccd485f4d2929b08 = function() { return handleError(function (arg0) {
        const ret = getObject(arg0).arrayBuffer();
        return addHeapObject(ret);
    }, arguments) };
    imports.wbg.__wbg_headers_0aeca08d4e61e2e7 = function(arg0) {
        const ret = getObject(arg0).headers;
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_newwithstrandinit_de7c409ec8538105 = function() { return handleError(function (arg0, arg1, arg2) {
        const ret = new Request(getStringFromWasm0(arg0, arg1), getObject(arg2));
        return addHeapObject(ret);
    }, arguments) };
    imports.wbg.__wbg_instanceof_Window_42f092928baaee84 = function(arg0) {
        const ret = getObject(arg0) instanceof Window;
        return ret;
    };
    imports.wbg.__wbg_fetch_9a5cb9d8a96004d0 = function(arg0, arg1) {
        const ret = getObject(arg0).fetch(getObject(arg1));
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_newnoargs_971e9a5abe185139 = function(arg0, arg1) {
        const ret = new Function(getStringFromWasm0(arg0, arg1));
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_new_ac586205e4424583 = function() {
        const ret = new Map();
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_call_33d7bcddbbfa394a = function() { return handleError(function (arg0, arg1) {
        const ret = getObject(arg0).call(getObject(arg1));
        return addHeapObject(ret);
    }, arguments) };
    imports.wbg.__wbg_new_e6a9fecc2bf26696 = function() {
        const ret = new Object();
        return addHeapObject(ret);
    };
    imports.wbg.__wbindgen_is_string = function(arg0) {
        const ret = typeof(getObject(arg0)) === 'string';
        return ret;
    };
    imports.wbg.__wbg_self_fd00a1ef86d1b2ed = function() { return handleError(function () {
        const ret = self.self;
        return addHeapObject(ret);
    }, arguments) };
    imports.wbg.__wbg_window_6f6e346d8bbd61d7 = function() { return handleError(function () {
        const ret = window.window;
        return addHeapObject(ret);
    }, arguments) };
    imports.wbg.__wbg_globalThis_3348936ac49df00a = function() { return handleError(function () {
        const ret = globalThis.globalThis;
        return addHeapObject(ret);
    }, arguments) };
    imports.wbg.__wbg_global_67175caf56f55ca9 = function() { return handleError(function () {
        const ret = global.global;
        return addHeapObject(ret);
    }, arguments) };
    imports.wbg.__wbindgen_is_undefined = function(arg0) {
        const ret = getObject(arg0) === undefined;
        return ret;
    };
    imports.wbg.__wbg_new_3ee7ebe9952c1fbd = function(arg0, arg1) {
        const ret = new Error(getStringFromWasm0(arg0, arg1));
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_call_65af9f665ab6ade5 = function() { return handleError(function (arg0, arg1, arg2) {
        const ret = getObject(arg0).call(getObject(arg1), getObject(arg2));
        return addHeapObject(ret);
    }, arguments) };
    imports.wbg.__wbg_set_a55cff623a9eaa21 = function(arg0, arg1, arg2) {
        const ret = getObject(arg0).set(getObject(arg1), getObject(arg2));
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_new_52205195aa880fc2 = function(arg0, arg1) {
        try {
            var state0 = {a: arg0, b: arg1};
            var cb0 = (arg0, arg1) => {
                const a = state0.a;
                state0.a = 0;
                try {
                    return __wbg_adapter_127(a, state0.b, arg0, arg1);
                } finally {
                    state0.a = a;
                }
            };
            const ret = new Promise(cb0);
            return addHeapObject(ret);
        } finally {
            state0.a = state0.b = 0;
        }
    };
    imports.wbg.__wbg_resolve_0107b3a501450ba0 = function(arg0) {
        const ret = Promise.resolve(getObject(arg0));
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_then_18da6e5453572fc8 = function(arg0, arg1) {
        const ret = getObject(arg0).then(getObject(arg1));
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_then_e5489f796341454b = function(arg0, arg1, arg2) {
        const ret = getObject(arg0).then(getObject(arg1), getObject(arg2));
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_buffer_34f5ec9f8a838ba0 = function(arg0) {
        const ret = getObject(arg0).buffer;
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_newwithbyteoffsetandlength_88fdad741db1b182 = function(arg0, arg1, arg2) {
        const ret = new Uint8Array(getObject(arg0), arg1 >>> 0, arg2 >>> 0);
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_new_cda198d9dbc6d7ea = function(arg0) {
        const ret = new Uint8Array(getObject(arg0));
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_set_1a930cfcda1a8067 = function(arg0, arg1, arg2) {
        getObject(arg0).set(getObject(arg1), arg2 >>> 0);
    };
    imports.wbg.__wbg_length_51f19f73d6d9eff3 = function(arg0) {
        const ret = getObject(arg0).length;
        return ret;
    };
    imports.wbg.__wbg_newwithlength_66e5530e7079ea1b = function(arg0) {
        const ret = new Uint8Array(arg0 >>> 0);
        return addHeapObject(ret);
    };
    imports.wbg.__wbg_set_2762e698c2f5b7e0 = function() { return handleError(function (arg0, arg1, arg2) {
        const ret = Reflect.set(getObject(arg0), getObject(arg1), getObject(arg2));
        return ret;
    }, arguments) };
    imports.wbg.__wbindgen_debug_string = function(arg0, arg1) {
        const ret = debugString(getObject(arg1));
        const ptr0 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        getInt32Memory0()[arg0 / 4 + 1] = len0;
        getInt32Memory0()[arg0 / 4 + 0] = ptr0;
    };
    imports.wbg.__wbindgen_throw = function(arg0, arg1) {
        throw new Error(getStringFromWasm0(arg0, arg1));
    };
    imports.wbg.__wbindgen_memory = function() {
        const ret = wasm.memory;
        return addHeapObject(ret);
    };
    imports.wbg.__wbindgen_closure_wrapper1383 = function(arg0, arg1, arg2) {
        const ret = makeMutClosure(arg0, arg1, 531, __wbg_adapter_26);
        return addHeapObject(ret);
    };

    return imports;
}

function initMemory(imports, maybe_memory) {

}

function finalizeInit(instance, module) {
    wasm = instance.exports;
    init.__wbindgen_wasm_module = module;
    cachedBigUint64Memory0 = new BigUint64Array();
    cachedInt32Memory0 = new Int32Array();
    cachedUint8Memory0 = new Uint8Array();


    return wasm;
}

function initSync(bytes) {
    const imports = getImports();

    initMemory(imports);

    const module = new WebAssembly.Module(bytes);
    const instance = new WebAssembly.Instance(module, imports);

    return finalizeInit(instance, module);
}

async function init(input) {
    if (typeof input === 'undefined') {
        input = new URL('arrow2_bg.wasm', import.meta.url);
    }
    const imports = getImports();

    if (typeof input === 'string' || (typeof Request === 'function' && input instanceof Request) || (typeof URL === 'function' && input instanceof URL)) {
        input = fetch(input);
    }

    initMemory(imports);

    const { instance, module } = await load(await input, imports);

    return finalizeInit(instance, module);
}

export { initSync }
export default init;