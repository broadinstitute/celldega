# PR #289: Row Group Storage Mode

## Summary

This PR introduces an optional **row group storage mode** for Celldega's LandscapeFiles. Instead of storing thousands of individual Parquet and WebP tile files, this mode consolidates all data into a small number of Parquet files using Apache Parquet's row group feature.

### Key Benefits
- **Reduced file count**: From 50,000+ files to ~10 files
- **Cloud hosting compatibility**: Works within GitHub/Hugging Face file limits
- **Efficient partial loading**: HTTP Range Requests fetch only needed data
- **Backwards compatible**: Opt-in via `use_row_groups=True` parameter

---

## High-Level Architecture

### Data Flow

```
Python Preprocessing (use_row_groups=True)
    ↓
Single Parquet files with multiple row groups
    ↓
JavaScript Frontend detects row group mode
    ↓
Formula-based indexing: row_group_index = tile_x * num_tiles_y + tile_y
    ↓
HTTP Range Requests fetch only visible tiles
```

### Storage Comparison

| Data Type | Traditional Mode | Row Group Mode |
|-----------|-----------------|----------------|
| Transcripts | ~7,500 files | 1 file (transcripts.parquet) |
| Cell Boundaries | ~7,500 files | 1 file (cell_segmentation.parquet) |
| Gene Expression | ~500 files | 1 file (cbg.parquet) |
| Image Tiles | ~40,000 files | 4 files (one per channel) |
| **Total** | **~55,000 files** | **~10 files** |

---

## File-by-File Changes

### Python Backend

#### `src/celldega/pre/run_pre_processing.py`
**Purpose**: Main preprocessing orchestrator

**Changes**:
- Added `use_row_groups` parameter to `main()` function
- Conditional logic to call row-group or traditional tile functions
- Image tile packing into Parquet when row groups enabled
- Passes `tile_grid_info` and `image_tile_info` to parameter saving

#### `src/celldega/pre/trx_tile.py`
**Purpose**: Transcript tile generation

**Changes**:
- New `make_trx_tiles_row_groups()` function
- `_collect_tile_data_for_row_groups()` collects all tiles in order
- `_write_tiles_as_row_groups()` writes single Parquet with row groups
- Schema consistency handling for empty tiles
- `write_statistics=False` for smaller footer

#### `src/celldega/pre/boundary_tile.py`
**Purpose**: Cell boundary tile generation

**Changes**:
- New `make_cell_boundary_tiles_row_groups()` function
- Parallel structure to transcript tiles
- Same formula-based indexing scheme
- Empty tile handling with consistent schema

#### `src/celldega/pre/landscape.py`
**Purpose**: CBG (cell-by-gene) data processing

**Changes**:
- New `save_cbg_gene_parquets_row_groups()` function
- One row group per gene (sorted alphabetically)
- Stores `gene_to_row_group` mapping in Parquet metadata
- Used by frontend for direct gene lookup

#### `src/celldega/pre/__init__.py`
**Purpose**: Module exports and utilities

**Changes**:
- New `pack_image_tiles_to_parquet()` function
- Reads DZI files for image dimensions
- Packs WebP tiles into Parquet row groups
- Deletes source tile directories (keeps .dzi files)
- Updated `save_landscape_parameters()` with row group config
- Exports new functions

### JavaScript Frontend

#### `js/read_parquet/pqInitializer.js`
**Purpose**: parquet-wasm initialization

**Changes**:
- Updated to use npm parquet-wasm 0.7.1 (from vendored 0.4.0-beta.5)
- Removed custom wasm loading, uses standard npm package
- Exposes version info for debugging

#### `js/read_parquet/row_group_tile_reader.js` (NEW)
**Purpose**: Read transcript/cell tiles from row-grouped Parquet

**Features**:
- `RowGroupTileReader` class
- Formula-based index computation
- HTTP Range Request support detection (`_checkRangeSupport()`)
- Streaming mode with fallback to full-file fetch
- `readTiles()` for batch tile reading

#### `js/read_parquet/cbg_row_group_reader.js` (NEW)
**Purpose**: Read gene expression data from row-grouped Parquet

**Features**:
- `CBGRowGroupReader` class
- Reads `gene_to_row_group` from Parquet schema metadata
- `readGene(geneName)` returns expression data for one gene
- Streaming with fallback support

#### `js/read_parquet/image_row_group_reader.js` (NEW)
**Purpose**: Read image tiles from row-grouped Parquet

**Features**:
- `ImageRowGroupReader` class
- Zoom-aware indexing with cumulative offsets
- Extracts binary image data, creates Blob URLs
- Tile caching to avoid re-creating Blob URLs
- `readTile(zoom, tileX, tileY)` returns Image object

#### `js/viz/landscape_ist.js`
**Purpose**: Main landscape visualization initialization

**Changes**:
- Imports new row group readers
- `initializeRowGroupReaders()` function
- Detects row group mode from `landscape_parameters.json`
- Initializes appropriate readers based on config
- Passes CBG reader to gene loading functions

#### `js/deck-gl/layers/image_layers.js`
**Purpose**: deck.gl image tile layers

**Changes**:
- `create_get_tile_data_from_parquet()` helper function
- Switches between traditional DeepZoom and Parquet-based loading
- Uses `ImageRowGroupReader.readTile()` for row group mode
- Preserves existing DeepZoom support for backwards compatibility

#### `js/global_variables/image_dimensions.js`
**Purpose**: Image dimension management

**Changes**:
- Multiple fallback strategies for dimension retrieval
- Reads from `.dzi` files (preferred)
- Falls back to `landscape_parameters.image_dimensions`
- Can calculate from zoom info as last resort

#### `js/global_variables/cell_exp_array.js`
**Purpose**: Cell expression data loading

**Changes**:
- Added optional `cbgReader` parameter
- Uses `cbgReader.readGene()` when available
- Falls back to individual file loading otherwise
- Updated function signature propagated to all callers

#### `js/vector_tile/transcripts/grab_trx_tiles_in_view.js`
**Purpose**: Fetch transcript tiles for visible viewport

**Changes**:
- Detects row group mode from `viz_state`
- Uses `RowGroupTileReader.readTiles()` for row group mode
- Falls back to individual file fetching otherwise

#### `js/vector_tile/polygons/grab_cell_tiles_in_view.js`
**Purpose**: Fetch cell boundary tiles for visible viewport

**Changes**:
- Same pattern as transcript tiles
- Uses cell segmentation row group reader
- Maintains backwards compatibility

### UI Components Updated for CBG Reader

The following files were updated to pass the CBG reader parameter:

- `js/ui/gene_search.js`
- `js/ui/bar_plot.js`
- `js/ui/switch_dataset.js`
- `js/viz/yearbook.js`
- `js/widget_interactions/update_ist_landscape_from_cgm.js`
- `js/deck-gl/layers/trx_layer.js`

### Build System

#### `package.json`
- Added `parquet-wasm: ^0.7.1` dependency (was vendored)

#### `wasm-plugin.mjs`
- Updated WASM loading for new parquet-wasm structure

#### `eslint.config.js`
- Minor linting configuration updates

### Documentation & Examples

#### `examples/row_grouped_parquet_example.py` (NEW)
- Standalone example showing row group creation
- Demonstrates reading specific row groups

#### `docs/overview/row_groups.md` (NEW)
- Comprehensive documentation for row group mode
- Usage instructions and configuration details

#### `docs/overview/file_formats.md`
- Added section on row group storage mode
- Link to detailed row groups documentation

---

## Technical Details

### Formula-Based Indexing

Row groups are organized deterministically:
```
row_group_index = tile_x * num_tiles_y + tile_y
```

This enables O(1) lookup without metadata scanning.

### HTTP Range Request Detection

Before attempting streaming, the frontend:
1. Sends HEAD request to check CORS headers
2. Verifies `Accept-Ranges: bytes` header
3. Falls back to full fetch if unavailable

This prevents WASM crashes from failed Range requests.

### Schema Consistency

Empty tiles are written with explicit schema to maintain:
- Consistent row group count
- Valid index positions
- Proper Arrow table structure

### Parquet Metadata

Stored in file schema metadata:
- `storage_mode`: "row_groups_formula" | "row_groups_cbg" | "row_groups_image"
- `tile_grid_info`: Grid dimensions for spatial tiles
- `gene_to_row_group`: Gene-to-index mapping for CBG
- `zoom_info`: Zoom level offsets for images

---

## Testing

### Manual Testing Checklist
- [ ] Traditional mode still works (use_row_groups=False)
- [ ] Row group mode preprocessing completes
- [ ] Transcript tiles load and display
- [ ] Cell boundaries load and display
- [ ] Gene selection colors cells correctly
- [ ] Image tiles display at all zoom levels
- [ ] Gene search works
- [ ] Cluster coloring works
- [ ] Pan/zoom performance acceptable

### Verification Commands
```python
# Preprocess with row groups
dega.pre.main(
    sample='Xenium_Sample',
    data_root_dir='data/',
    path_landscape_files='output/',
    use_row_groups=True
)

# Check output files
import os
for f in os.listdir('output/'):
    print(f)
# Expected: transcripts.parquet, cell_segmentation.parquet, cbg.parquet, etc.
```

---

## Migration Notes

- **No breaking changes**: Default behavior unchanged
- **Opt-in**: Set `use_row_groups=True` to enable
- **Reprocessing required**: Cannot convert existing files; must rerun preprocessing
- **Mixed datasets OK**: Different datasets can use different modes
