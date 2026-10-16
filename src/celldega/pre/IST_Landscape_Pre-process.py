import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

import celldega as dega
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
import scanpy as sc
import tifffile
from matplotlib.colors import to_hex
from scipy.sparse import coo_matrix
from shapely.geometry import Polygon

import xml.etree.ElementTree as ET

def main(
    data_dir,
    sample,
    path_landscape_files,
    tile_size=500,
    image_scale=1.0,
    jitter=1,
):
    # helper functions
    def safe_polygon(row):
        try:
            return Polygon(zip(row["vertex_x"], row["vertex_y"]))
        except Exception as _e:
            # print(f"Error processing row {row.name}: {_e}")
            return Polygon()

    def simple_format(geometry, image_scale):
        # factor in scaling
        return [
            [[coord[0] / image_scale, coord[1] / image_scale] for coord in polygon]
            for polygon in geometry
        ]

    def transform_polygon(polygon):
        exterior_coords = polygon.exterior.coords
        original_format_coords = np.array([np.array(coord) for coord in exterior_coords])
        return np.array([original_format_coords], dtype=object)

    def make_column_names_unique_fast(df):
        counts = defaultdict(int)
        used = set()
        new_cols = []

        for col in df.columns:
            if col not in used:
                new_cols.append(col)
                used.add(col)
                counts[col] += 1
            else:
                while True:
                    new_name = f"{col}_{counts[col]}"
                    counts[col] += 1
                    if new_name not in used:
                        new_cols.append(new_name)
                        used.add(new_name)
                        break

        df.columns = new_cols
        return df

    print(f"Celldega version: {dega.__version__}")

    image_tile_layer = "h&e"
    suffix = ".webp[Q=100]"

    path_landscape_files = path_landscape_files + "/" + sample
    os.makedirs(path_landscape_files, exist_ok=True)

    print("Processing Image...")

    # Image
    img_file_path = (
        f"{data_dir}/{sample}/{sample}.ome.tiff"
    )

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

    print("Processing Cells...")

    # Cells
    # cells = pd.read_csv(
    #     f"{data_dir}/"
    #     f"{sample}/{sample}_cell_binned/barcodes.tsv.gz",
    #     sep="\t",
    #     header=None,
    #     index_col=0,
    # )

    gc = pd.read_csv(
        f"{data_dir}/{sample}/sample_prep_stats_sample.csv",
        index_col=0,
    )

    # tmp_ini = pd.DataFrame([x.split(":") for x in cells.index.tolist()])
    # tmp_ini.set_index(0, inplace=True)
    # tmp_ini.index.name = None
    # tmp_ini.columns = ["x", "y"]
    # tmp_ini = tmp_ini.astype(float)

    # tmp = pd.DataFrame()
    # tmp["x"] = tmp_ini["y"]
    # tmp["y"] = tmp_ini["x"]

    # tmp["x"] = (tmp["x"] - gc.loc[sample, "Global_left"]) * high_res_scale
    # tmp["y"] = (tmp["y"] - gc.loc[sample, "Global_top"]) * high_res_scale

    # tmp["geometry"] = tmp.apply(lambda row: [row["x"], row["y"]], axis=1)
    # tmp["name"] = pd.Series(tmp.index.tolist(), index=tmp.index.tolist())

    # tmp[["name", "geometry"]].to_parquet(
    #     path_landscape_files + "/cell_metadata.parquet"
    # )

    # clusters = pd.DataFrame(index=tmp.index.tolist())
    # clusters["cluster"] = pd.Series(0, index=tmp.index.tolist())

    # cell_clusters_dir = path_landscape_files + "/cell_clusters"
    # os.makedirs(cell_clusters_dir, exist_ok=True)
    # clusters.to_parquet(f"{cell_clusters_dir}/cluster.parquet")

    # Segmented Cells
    tile_bounds = {"x_min": 0, "x_max": 55000, "y_min": 0, "y_max": 55000}

    poly = pd.read_csv(
        f"{data_dir}/{sample}/"
        f"{sample}_Expanded_5um_cell_contour_coords.csv"
    )

    poly["vertex_x"] = (poly["vertex_x"] - gc.loc[sample, "Global_left"]) * (
        high_res_scale
    )
    poly["vertex_y"] = (poly["vertex_y"] - gc.loc[sample, "Global_top"]) * (
        high_res_scale
    )

    grouped = poly.groupby("cell_id").agg(list)
    grouped["geometry"] = grouped.apply(safe_polygon, axis=1)

    cells = gpd.GeoDataFrame(grouped, geometry="geometry")[["geometry"]]
    cells["NEW_GEOMETRY"] = cells["geometry"].apply(lambda poly: transform_polygon(poly))
    cells["GEOMETRY"] = cells["NEW_GEOMETRY"].apply(
        lambda x: simple_format(x, image_scale)
    )
    cells["polygon"] = cells["GEOMETRY"].apply(lambda x: Polygon(x[0]))

    gdf_cells = gpd.GeoDataFrame(geometry=cells["polygon"])
    gdf_cells["center_x"] = gdf_cells.centroid.x
    gdf_cells["center_y"] = gdf_cells.centroid.y

    cell_segmentation_dir = path_landscape_files + "/cell_segmentation"
    os.makedirs(cell_segmentation_dir, exist_ok=True)

    gdf_cells.index = "cell" + gdf_cells.index.astype(str)
    cells.index = "cell" + cells.index.astype(str)

    clusters = pd.DataFrame(index=gdf_cells.index.tolist())
    clusters["cluster"] = pd.Series(0, index=gdf_cells.index.tolist())

    cell_clusters_dir = path_landscape_files + "/cell_clusters"
    os.makedirs(cell_clusters_dir, exist_ok=True)
    clusters.to_parquet(f"{cell_clusters_dir}/cluster.parquet")

    gdf_cells_copy = gdf_cells.copy()

    gdf_cells_copy.reset_index(inplace=True)
    gdf_cells_copy.rename(columns={"cell_id":"name"}, inplace=True)

    gdf_cells_copy["geometry"] = gdf_cells_copy.apply(lambda row: [row["center_x"], row["center_y"]], axis=1)

    gdf_cells_copy[["name", "geometry"]].to_parquet(
        path_landscape_files + "/cell_metadata.parquet"
    )

    cell_str_to_int_mapping = dega.pre.boundary_tile._get_name_mapping(
        path_landscape_files, layer="boundary", segmentation="default"
    )

    gdf_cells.index = gdf_cells.index.astype(str).map(cell_str_to_int_mapping)
    cells.index = cells.index.astype(str).map(cell_str_to_int_mapping)

    tile_size_x = tile_size
    tile_size_y = tile_size

    n_tiles_x = int(np.ceil((tile_bounds["x_max"] - tile_bounds["x_min"]) / tile_size_x))
    n_tiles_y = int(np.ceil((tile_bounds["y_max"] - tile_bounds["y_min"]) / tile_size_y))

    for i in range(n_tiles_x):
        if i % 2 == 0:
            print("row", i)

        for j in range(n_tiles_y):
            tile_x_min = tile_bounds["x_min"] + i * tile_size_x
            tile_x_max = tile_x_min + tile_size_x
            tile_y_min = tile_bounds["y_min"] + j * tile_size_y
            tile_y_max = tile_y_min + tile_size_y

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

    print("Processing Genes...")

    # Meta Gene
    adata_cell = sc.read_10x_mtx(
        f"{data_dir}/"
        f"{sample}/{sample}_cell_binned/"
    )

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

    print("Saving Landscape Parameters...")

    # Save Landscape Parameters
    max_pyramid_zoom = dega.pre.get_max_zoom_level(
        path_landscape_files + f"/pyramid_images/{image_tile_layer}_files"
    )

    landscape_parameters = {
        "technology": "IST",
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

    print("Saving Clusters...")

    # Meta Cluster
    meta_cluster = pd.DataFrame()
    meta_cluster.loc["0", "color"] = "#ff7f0e"
    meta_cluster.loc["0", "count"] = 1000
    meta_cluster.to_parquet(cell_clusters_dir + "/meta_cluster.parquet")

    print("Processing CBG...")

    # Cell-by-gene (CBG)
    path_cbg = (
        f"{data_dir}/"
        f"{sample}/{sample}_cell_binned/"
    )
    cbg = dega.pre.read_cbg_mtx(path_cbg, technology="IST")
    cbg.index = [x.split(":")[0] for x in cbg.index.tolist()]
    cbg = make_column_names_unique_fast(cbg)

    dega.pre.make_meta_gene(cbg, path_landscape_files + "/meta_gene.parquet")
    dega.pre.save_cbg_gene_parquets("IST", path_landscape_files, cbg, verbose=True)

    print("Processing Jittered Transcripts...")

    # Jittered transcripts
    sbg = dega.pre.landscape.read_cbg_mtx(
        f"{data_dir}/"
        f"{sample}/{sample}_raw",
        technology="IST",
        # barcodes_name="coords",
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

    tile_bounds = {"x_min": 0, "x_max": 55000, "y_min": 0, "y_max": 55000}
    n_tiles_x = int(np.ceil((tile_bounds["x_max"] - tile_bounds["x_min"]) / tile_size))
    n_tiles_y = int(np.ceil((tile_bounds["y_max"] - tile_bounds["y_min"]) / tile_size))

    sbg.reset_index(inplace=True)
    spots.index = sbg.index
    del sbg[0]
    sbg = make_column_names_unique_fast(sbg)

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
        rng=np.random.default_rng() # np.random.Generator
    )

    print("Done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="IST-Celldega-LandscapeFiles-Preprocess"
    )
    parser.add_argument("--data_dir", type=str)
    parser.add_argument("--sample", type=str)
    parser.add_argument("--path_landscape_files", type=str)
    parser.add_argument("--tile_size", type=int)
    parser.add_argument("--image_scale", type=float)
    parser.add_argument("--jitter", type=int)
    args = parser.parse_args()

    main(
        data_dir=args.data_dir,
        sample=args.sample,
        path_landscape_files=args.path_landscape_files,
        tile_size=args.tile_size,
        image_scale=args.image_scale,
        jitter=args.jitter,
    )