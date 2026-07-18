import argparse
import json
import os
import xml.etree.ElementTree as ET

import celldega as dega
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scanpy as sc
import tifffile
from matplotlib.colors import to_hex
from shapely.geometry import Polygon

DEFAULT_TILE_BOUNDS = {"x_min": 0, "x_max": 55000, "y_min": 0, "y_max": 55000}


def _safe_polygon(row):
    try:
        return Polygon(zip(row["vertex_x"], row["vertex_y"]))
    except Exception as _e:
        # print(f"Error processing row {row.name}: {_e}")
        return Polygon()


def _simple_format(geometry, image_scale):
    # factor in scaling
    return [
        [[coord[0] / image_scale, coord[1] / image_scale] for coord in polygon]
        for polygon in geometry
    ]


def _transform_polygon(polygon):
    exterior_coords = polygon.exterior.coords
    original_format_coords = np.array([np.array(coord) for coord in exterior_coords])
    return np.array([original_format_coords], dtype=object)


def _tile_grid_shape(tile_bounds, tile_size):
    n_tiles_x = int(np.ceil((tile_bounds["x_max"] - tile_bounds["x_min"]) / tile_size))
    n_tiles_y = int(np.ceil((tile_bounds["y_max"] - tile_bounds["y_min"]) / tile_size))
    return n_tiles_x, n_tiles_y


def _load_prep_stats(data_dir, sample):
    return pd.read_csv(
        f"{data_dir}/{sample}/sample_prep_stats_sample.csv", index_col=0
    )


def _process_image(data_dir, sample, path_landscape_files, image_tile_layer, suffix):
    """Convert the OME-TIFF H&E image into a deepzoom pyramid; return the micron-to-pixel scale."""
    img_file_path = f"{data_dir}/{sample}/{sample}.ome.tiff"

    with tifffile.TiffFile(img_file_path) as tif:
        series = tif.series[0]
        image_data = series.asarray()
        root = ET.fromstring(tif.ome_metadata)

        pixels = root.find(".//{*}Image[@ID='Image:RegImage_20x_pyramid']/{*}Pixels")
        scaling_factor = float(pixels.attrib["PhysicalSizeX"]) / 1000

    high_res_scale = 1 / scaling_factor

    tifffile.imwrite(
        path_landscape_files + "/output_regular.tif", image_data, compression=None
    )
    image_png = dega.pre._convert_to_png(path_landscape_files + "/output_regular.tif")
    dega.pre.make_deepzoom_pyramid(
        image_png,
        path_landscape_files + "/pyramid_images/",
        image_tile_layer,
        suffix=suffix,
    )

    return high_res_scale


def _process_cell_segmentation(
    data_dir,
    sample,
    path_landscape_files,
    gc,
    high_res_scale,
    image_scale,
    tile_size,
    tile_bounds,
):
    """Build per-cell polygons from the expanded contour CSV; write metadata, clusters, and segmentation tiles."""
    poly = pd.read_csv(
        f"{data_dir}/{sample}/{sample}_Expanded_5um_cell_contour_coords.csv"
    )

    poly["vertex_x"] = (poly["vertex_x"] - gc.loc[sample, "Global_left"]) * high_res_scale
    poly["vertex_y"] = (poly["vertex_y"] - gc.loc[sample, "Global_top"]) * high_res_scale

    grouped = poly.groupby("cell_id").agg(list)
    grouped["geometry"] = grouped.apply(_safe_polygon, axis=1)

    cells = gpd.GeoDataFrame(grouped, geometry="geometry")[["geometry"]]
    cells["NEW_GEOMETRY"] = cells["geometry"].apply(_transform_polygon)
    cells["GEOMETRY"] = cells["NEW_GEOMETRY"].apply(lambda x: _simple_format(x, image_scale))
    cells["polygon"] = cells["GEOMETRY"].apply(lambda x: Polygon(x[0]))

    gdf_cells = gpd.GeoDataFrame(geometry=cells["polygon"])
    gdf_cells["center_x"] = gdf_cells.centroid.x
    gdf_cells["center_y"] = gdf_cells.centroid.y

    cell_segmentation_dir = path_landscape_files + "/cell_segmentation"
    os.makedirs(cell_segmentation_dir, exist_ok=True)

    gdf_cells.index = "cell" + gdf_cells.index.astype(str)
    cells.index = "cell" + cells.index.astype(str)

    cell_clusters_dir = path_landscape_files + "/cell_clusters"
    os.makedirs(cell_clusters_dir, exist_ok=True)

    clusters = pd.DataFrame(index=gdf_cells.index.tolist())
    clusters["cluster"] = pd.Series(0, index=gdf_cells.index.tolist())
    clusters.to_parquet(f"{cell_clusters_dir}/cluster.parquet")

    gdf_cells_copy = gdf_cells.copy()
    gdf_cells_copy.reset_index(inplace=True)
    gdf_cells_copy.rename(columns={"cell_id": "name"}, inplace=True)
    gdf_cells_copy["geometry"] = gdf_cells_copy.apply(
        lambda row: [row["center_x"], row["center_y"]], axis=1
    )

    gdf_cells_copy[["name", "geometry"]].to_parquet(
        path_landscape_files + "/cell_metadata.parquet"
    )

    cell_str_to_int_mapping = dega.pre.boundary_tile._get_name_mapping(
        path_landscape_files, layer="boundary", segmentation="default"
    )

    gdf_cells.index = gdf_cells.index.astype(str).map(cell_str_to_int_mapping)
    cells.index = cells.index.astype(str).map(cell_str_to_int_mapping)

    n_tiles_x, n_tiles_y = _tile_grid_shape(tile_bounds, tile_size)

    for i in range(n_tiles_x):
        if i % 2 == 0:
            print("row", i)

        for j in range(n_tiles_y):
            tile_x_min = tile_bounds["x_min"] + i * tile_size
            tile_x_max = tile_x_min + tile_size
            tile_y_min = tile_bounds["y_min"] + j * tile_size
            tile_y_max = tile_y_min + tile_size

            keep_cells = gdf_cells[
                (gdf_cells.center_x >= tile_x_min)
                & (gdf_cells.center_x < tile_x_max)
                & (gdf_cells.center_y >= tile_y_min)
                & (gdf_cells.center_y < tile_y_max)
            ].index.tolist()

            inst_geo = cells.loc[keep_cells, ["GEOMETRY"]]
            inst_geo["name"] = pd.Series(
                inst_geo.index.tolist(), index=inst_geo.index.tolist()
            )

            filename = f"{cell_segmentation_dir}/cell_tile_{i}_{j}.parquet"
            if inst_geo.shape[0] > 0:
                inst_geo[["GEOMETRY", "name"]].to_parquet(filename)

    return cell_clusters_dir


def _process_gene_metadata(data_dir, sample, path_landscape_files):
    """Write a placeholder meta_gene.parquet with a tab-colormap color assigned per gene."""
    adata_cell = sc.read_10x_mtx(f"{data_dir}/{sample}/{sample}_cell_binned/")

    list_genes = adata_cell.var.index.tolist()
    meta_gene = pd.DataFrame(index=list_genes)

    palettes = [plt.get_cmap(name).colors for name in plt.colormaps() if "tab" in name]
    flat_colors = [color for palette in palettes for color in palette]
    flat_colors_hex = [to_hex(color) for color in flat_colors]

    colors = [
        flat_colors_hex[i % len(flat_colors_hex)] if "Blank" not in gene else "#FFFFFF"
        for i, gene in enumerate(list_genes)
    ]

    ser_color = pd.Series(colors, index=list_genes)

    meta_gene["mean"] = pd.Series(100, index=list_genes)
    meta_gene["std"] = pd.Series(10, index=list_genes)
    meta_gene["max"] = pd.Series(100, index=list_genes)
    meta_gene["non-zero"] = pd.Series(0.5, index=list_genes)
    meta_gene["color"] = ser_color

    meta_gene.to_parquet(path_landscape_files + "/meta_gene.parquet")


def _save_landscape_parameters(path_landscape_files, image_tile_layer, tile_size, technology):
    max_pyramid_zoom = dega.pre.get_max_zoom_level(
        path_landscape_files + f"/pyramid_images/{image_tile_layer}_files"
    )

    landscape_parameters = {
        "technology": technology,
        "segmentation_approach": ["default"],
        "max_pyramid_zoom": max_pyramid_zoom,
        "tile_size": tile_size,
        "image_info": [
            {
                "name": image_tile_layer,
                "button_name": image_tile_layer.upper(),
                "color": [0, 0, 255],
            }
        ],
        "image_format": ".webp",
        "use_int_index": True,
    }

    with open(path_landscape_files + "/landscape_parameters.json", "w") as f:
        json.dump(landscape_parameters, f, indent=2)


def _save_dummy_meta_cluster(cell_clusters_dir):
    meta_cluster = pd.DataFrame()
    meta_cluster.loc["0", "color"] = "#ff7f0e"
    meta_cluster.loc["0", "count"] = 1000
    meta_cluster.to_parquet(cell_clusters_dir + "/meta_cluster.parquet")


def _process_cbg(data_dir, sample, path_landscape_files, technology):
    """Read the per-cell gene matrix, dedupe gene names, and write per-gene CBG parquet files."""
    path_cbg = f"{data_dir}/{sample}/{sample}_cell_binned/"
    cbg = dega.pre.read_cbg_mtx(path_cbg, technology=technology)
    cbg.index = [x.split(":")[0] for x in cbg.index.tolist()]
    cbg = dega.pre.make_column_names_unique(cbg)

    dega.pre.make_meta_gene(cbg, path_landscape_files + "/meta_gene.parquet")
    dega.pre.save_cbg_gene_parquets(technology, path_landscape_files, cbg, verbose=True)


def _process_transcripts(
    data_dir,
    sample,
    path_landscape_files,
    gc,
    high_res_scale,
    tile_size,
    jitter,
    tile_bounds,
    technology,
):
    """Recover per-transcript coordinates from the raw sparse matrix; write jittered pseudo-transcript tiles."""
    sbg = dega.pre.read_cbg_mtx(
        f"{data_dir}/{sample}/{sample}_raw",
        technology=technology,
        barcodes_name="barcodes",
    )

    coords = sbg.index.tolist()
    tmp = [x.split(":") for x in coords]
    tmp = [[x for x in row if x.isdigit()] for row in tmp]
    df_tmp = pd.DataFrame(tmp, dtype=float)
    df_tmp = df_tmp / 1000
    df_tmp.columns = ["y", "x"]

    df_tmp["x"] = (df_tmp["x"] - gc.loc[sample, "Global_left"]) * high_res_scale
    df_tmp["y"] = (df_tmp["y"] - gc.loc[sample, "Global_top"]) * high_res_scale

    spots = df_tmp
    gene_str_to_int = dega.pre.boundary_tile._get_name_mapping(
        path_landscape_files, layer="transcript"
    )

    sbg.reset_index(inplace=True)
    spots.index = sbg.index
    del sbg[0]
    sbg = dega.pre.make_column_names_unique(sbg)

    trx_files_path = path_landscape_files + "/transcript_tiles"
    os.makedirs(trx_files_path, exist_ok=True)

    dega.pre.write_pseudotranscripts_from_sbg(
        spots=spots,
        sbg=sbg,
        gene_str_to_int=gene_str_to_int,
        tile_bounds=tile_bounds,
        tile_size=tile_size,
        path_output=trx_files_path,
        jitter=jitter,
        coarse_tile_factor=10,
        rng=np.random.default_rng(),  # np.random.Generator
    )


def main(
    data_dir,
    sample,
    path_landscape_files,
    tile_size=500,
    image_scale=1.0,
    jitter=1,
):
    print(f"Celldega version: {dega.__version__}")

    technology = "StrataMap"
    image_tile_layer = "h&e"
    suffix = ".webp[Q=100]"

    path_landscape_files = path_landscape_files + "/" + sample
    os.makedirs(path_landscape_files, exist_ok=True)

    print("Processing Image...")
    high_res_scale = _process_image(
        data_dir, sample, path_landscape_files, image_tile_layer, suffix
    )

    print("Processing Cells...")
    gc = _load_prep_stats(data_dir, sample)
    cell_clusters_dir = _process_cell_segmentation(
        data_dir,
        sample,
        path_landscape_files,
        gc,
        high_res_scale,
        image_scale,
        tile_size,
        dict(DEFAULT_TILE_BOUNDS),
    )

    print("Processing Genes...")
    _process_gene_metadata(data_dir, sample, path_landscape_files)

    print("Saving Landscape Parameters...")
    _save_landscape_parameters(path_landscape_files, image_tile_layer, tile_size, technology)

    print("Saving Clusters...")
    _save_dummy_meta_cluster(cell_clusters_dir)

    print("Processing CBG...")
    _process_cbg(data_dir, sample, path_landscape_files, technology)

    print("Processing Jittered Transcripts...")
    _process_transcripts(
        data_dir,
        sample,
        path_landscape_files,
        gc,
        high_res_scale,
        tile_size,
        jitter,
        dict(DEFAULT_TILE_BOUNDS),
        technology,
    )

    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="StrataMap-Celldega-LandscapeFiles-Preprocess"
    )
    parser.add_argument("--data_dir", type=str, required=True)
    parser.add_argument("--sample", type=str, required=True)
    parser.add_argument("--path_landscape_files", type=str, required=True)
    parser.add_argument("--tile_size", type=int, default=500)
    parser.add_argument("--image_scale", type=float, default=1.0)
    parser.add_argument("--jitter", type=int, default=1)
    args = parser.parse_args()

    main(
        data_dir=args.data_dir,
        sample=args.sample,
        path_landscape_files=args.path_landscape_files,
        tile_size=args.tile_size,
        image_scale=args.image_scale,
        jitter=args.jitter,
    )
