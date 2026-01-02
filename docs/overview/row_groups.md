# Row Group Storage Mode

## Overview

Celldega supports an optional **row group storage mode** that consolidates tile-based data into single Parquet files using Apache Parquet's row group feature. Instead of storing thousands of individual tile files, this mode stores all tiles as row groups within a single file per data type.

This approach offers significant advantages for cloud hosting platforms that have file count limitations (e.g., GitHub, Hugging Face) while maintaining comparable performance through HTTP Range Requests.

## Why Row Groups?

### The Problem with Many Small Files
Traditional LandscapeFiles store each tile as an individual Parquet file:
- Transcript tiles: `transcript_tiles/tile_X_Y.parquet` (potentially thousands of files)
- Cell boundaries: `cell_segmentation/tile_X_Y.parquet` (thousands of files)
- Gene expression: `cbg/GENE_NAME.parquet` (hundreds of files)
- Image tiles: `pyramid_images/channel_files/zoom/X_Y.webp` (tens of thousands of files)

For a typical Xenium dataset, this can result in **50,000+ files**, which:
- Exceeds file limits on platforms like GitHub (100,000 files)
- Creates overhead in file system operations
- Complicates data distribution and hosting

### The Row Group Solution
Row groups allow storing multiple logical "tiles" within a single physical file:
- Each row group corresponds to one tile/gene/image
- Row groups can be read independently via byte-range offsets
- HTTP Range Requests enable fetching only the needed row groups
- Total file count reduced from 50,000+ to ~10 files

## Enabling Row Group Mode

### Python Preprocessing

Enable row group mode by setting `use_row_groups=True` when running preprocessing:

```python
import celldega as dega

dega.pre.main(
    sample='Xenium_Sample',
    data_root_dir='data/xenium_data/',
    tile_size=250,
    path_landscape_files='data/landscape_files/my_sample_row_groups',
    use_int_index=True,
    use_row_groups=True  # Enable row group mode
)
```

### Command Line

```bash
python -m celldega.pre.run_pre_processing \
    --sample Xenium_Sample \
    --data_root_dir data/xenium_data/ \
    --path_landscape_files data/landscape_files/my_sample_row_groups \
    --use_row_groups True
```

## File Structure Comparison

### Traditional Mode (Individual Files)
```
landscape_files/
├── cbg/
│   ├── GENE1.parquet
│   ├── GENE2.parquet
│   └── ... (hundreds of files)
├── cell_segmentation/
│   ├── tile_0_0.parquet
│   ├── tile_0_1.parquet
│   └── ... (thousands of files)
├── transcript_tiles/
│   ├── tile_0_0.parquet
│   ├── tile_0_1.parquet
│   └── ... (thousands of files)
├── pyramid_images/
│   ├── dapi.dzi
│   ├── dapi_files/
│   │   ├── 0/
│   │   ├── 1/
│   │   └── ... (tens of thousands of WebP files)
│   └── ...
└── landscape_parameters.json
```

### Row Group Mode (Consolidated Files)
```
landscape_files/
├── cbg.parquet                    # All genes as row groups
├── transcripts.parquet            # All transcript tiles as row groups
├── cell_segmentation.parquet      # All cell tiles as row groups
├── pyramid_images/
│   ├── dapi.dzi                   # Metadata preserved
│   ├── dapi.parquet               # All image tiles as row groups
│   ├── rna.dzi
│   ├── rna.parquet
│   └── ...
└── landscape_parameters.json      # Updated with row group info
```

## How It Works

### Formula-Based Indexing

Row groups are organized using a deterministic indexing scheme that allows direct lookup without parsing metadata:

```
row_group_index = tile_x * num_tiles_y + tile_y
```

For example, with a grid of 137×55 tiles:
- Tile (0, 0) → Row group 0
- Tile (0, 1) → Row group 1
- Tile (1, 0) → Row group 55
- Tile (136, 54) → Row group 7534

This formula enables the frontend to compute exactly which row groups to fetch based on the visible viewport, without needing to scan file metadata.

### HTTP Range Requests

When hosted on a server that supports Range requests (most cloud storage does), the frontend uses `parquet-wasm`'s streaming capabilities to fetch only the needed row groups:

1. Frontend calculates which tiles are in view
2. Computes row group indices using the formula
3. Issues Range requests for just those row groups
4. Parquet-wasm fetches only the required bytes

This provides performance comparable to individual files while maintaining a single consolidated file.

### Fallback Mode

If the server doesn't support Range requests (e.g., local development servers), the frontend automatically falls back to:
1. Downloading the entire Parquet file once
2. Caching it in memory
3. Reading specific row groups from the cached data

## landscape_parameters.json Updates

When `use_row_groups=True`, the `landscape_parameters.json` includes additional configuration:

```json
{
    "technology": "Xenium",
    "use_row_groups": true,
    "tile_grid": {
        "num_tiles_x": 137,
        "num_tiles_y": 55,
        "tile_size": 250
    },
    "row_group_files": {
        "transcripts": "transcripts.parquet",
        "cell_segmentation": "cell_segmentation.parquet",
        "cbg": "cbg.parquet",
        "images": {
            "dapi": {
                "path": "pyramid_images/dapi.parquet",
                "zoom_info": { ... },
                "zoom_levels": [0, 1, 2, ..., 16]
            },
            "rna": {
                "path": "pyramid_images/rna.parquet",
                "zoom_info": { ... },
                "zoom_levels": [0, 1, 2, ..., 16]
            }
        }
    },
    "image_dimensions": {
        "width": 34375,
        "height": 13750,
        "tile_size": 256
    },
    "max_pyramid_zoom": 16
}
```

## Data Types Supported

### Transcripts (`transcripts.parquet`)
- One row group per spatial tile
- Columns: `name` (gene), `geometry` (coordinates), `tile_x`, `tile_y`
- Empty tiles are preserved as empty row groups for index consistency

### Cell Boundaries (`cell_segmentation.parquet`)
- One row group per spatial tile
- Columns: `cell_id`, `GEOMETRY` (polygon), `name`, `tile_x`, `tile_y`
- Same grid as transcripts for consistent indexing

### Cell-by-Gene (`cbg.parquet`)
- One row group per gene (sorted alphabetically)
- Columns: `cell_id`, `expression`, `gene`
- Gene-to-row-group mapping stored in Parquet metadata

### Image Tiles (`pyramid_images/<channel>.parquet`)
- One row group per image tile across all zoom levels
- Columns: `image_data` (binary), `zoom`, `tile_x`, `tile_y`
- Zoom-aware indexing with cumulative offsets
- Original WebP tile directories deleted; `.dzi` files preserved

## Performance Considerations

### Advantages
- **Reduced file count**: 50,000+ files → ~10 files
- **Better hosting compatibility**: Works with GitHub, Hugging Face limits
- **Efficient streaming**: HTTP Range Requests fetch only needed data
- **Simpler distribution**: Fewer files to manage and transfer

### Trade-offs
- **Footer size**: Large datasets require reading Parquet footer (~100KB-1MB)
- **Initial overhead**: First request includes footer parsing
- **Memory in fallback mode**: Full file loaded if Range requests unavailable

### Optimizations Applied
- `write_statistics=False` reduces footer size by ~50%
- Deterministic indexing eliminates metadata scanning
- Automatic fallback ensures compatibility

## Scalability

For very large datasets (>500M transcripts):
- Consider regional Parquet files (one per section)
- Use coarser tiles to reduce row group count
- Host on Range-request-supporting servers for best performance

## Backwards Compatibility

- Row group mode is **opt-in** via `use_row_groups=True`
- Default behavior (`use_row_groups=False`) unchanged
- Frontend auto-detects mode from `landscape_parameters.json`
- Both modes can coexist in different datasets
