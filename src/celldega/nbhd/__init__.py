"""
Module for performing neighborhood analysis.
"""

from libpysal.cg import alpha_shape as libpysal_alpha_shape
import geopandas as gpd
from shapely.ops import transform
import numpy as np
import json
import rasterio
from rasterio.features import rasterize
from shapely.geometry import Point, Polygon, MultiPolygon, box, shape, mapping
from shapely.affinity import affine_transform
from shapely.affinity import translate
import os
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
from skimage.io import imread
import pandas as pd
from itertools import combinations
from celldega.pre.boundary_tile import batch_transform_geometries


def _classify_polygons_contains_check(polygons, points):
    """
    Classifies polygons as "real" or "fake" based on whether they contain any points inside.

    Parameters:
    - polygons: GeoSeries of polygons (GeoPandas)
    - points: Array-like of point coordinates (e.g., numpy array or list of tuples)

    Returns:
    - GeoSeries of curated polygons
    """
    # Convert points to GeoDataFrame
    points_gdf = gpd.GeoDataFrame(geometry=[Point(p) for p in points])

    # Spatial join: Find points inside each polygon
    gdf_poly = gpd.GeoDataFrame(geometry=polygons)
    joined = gpd.sjoin(points_gdf, gdf_poly, predicate="within")

    # Get indices of polygons that contain at least one point
    real_polygons_indices = joined["index_right"].unique()

    # Filter polygons: Keep only those that contain points
    curated_polygons = gdf_poly.iloc[real_polygons_indices]

    return curated_polygons


def _verify_polygons_with_alpha_bulk(polygons, points, alpha, area_tolerance=0.05):
    """
    Verifies polygons by recalculating alpha shapes and ensuring agreement, using bulk spatial queries.

    Parameters:
    - polygons: GeoSeries of polygons (GeoPandas)
    - points: Array-like of point coordinates (e.g., numpy array or list of tuples)
    - alpha: Alpha value for recalculating alpha shapes

    Returns:
    - GeoSeries of curated polygons
    """
    curated_polygons = []
    points_gdf = gpd.GeoDataFrame(geometry=[Point(p) for p in points])

    # Build spatial index for points
    points_sindex = points_gdf.sindex

    for poly in polygons:
        # Bulk query to get candidate points
        possible_matches_index = list(points_sindex.query(poly, predicate="intersects"))

        # Extract points that intersect (including points on the boundary)
        contained_points = points_gdf.iloc[possible_matches_index]

        if len(contained_points) < 4:
            # If too few points, skip recalculation (consider this polygon invalid)
            continue

        # Convert contained points to a NumPy array of coordinates
        coords = np.array([p.coords[0] for p in contained_points.geometry])

        # Recalculate alpha shape for the points
        recalculated_alpha = libpysal_alpha_shape(coords, alpha)

        # check that there is a geometry
        if recalculated_alpha.shape[0] > 0:
            recalculated_area = recalculated_alpha.area.values[0]
            original_area = poly.area

            # Compute fractional difference in area
            area_difference = abs(recalculated_area - original_area) / original_area

            if area_difference <= area_tolerance:
                curated_polygons.append(poly)

    return gpd.GeoSeries(curated_polygons, crs=polygons.crs)



def alpha_shape(points, inv_alpha):

    poly = libpysal_alpha_shape(points, 1/inv_alpha)

    gdf_curated = _classify_polygons_contains_check(poly.values, points)

    validated_poly = _verify_polygons_with_alpha_bulk(
        gdf_curated.geometry.values,
        points,
        1/inv_alpha
    )

    multi_poly = MultiPolygon(validated_poly.values)

    return multi_poly



def _round_coordinates(geometry, precision=2):
    """
    Round the coordinates of a Shapely geometry to the specified precision.

    Parameters:
    - geometry: Shapely geometry object (e.g., Polygon, MultiPolygon).
    - precision: Number of decimal places to round to.

    Returns:
    - Rounded Shapely geometry.
    """
    if geometry is None:
        return None

    def round_coords(x, y, z=None):
        if z is not None:
            return (round(x, precision), round(y, precision), round(z, precision))
        return (round(x, precision), round(y, precision))

    return transform(round_coords, geometry)


def alpha_shape_cell_clusters(meta_cell, cat='cluster', alphas=[100, 150, 200, 250, 300, 350]):

    """
    Compute alpha shapes for each cluster in the cell metadata.

    Parameters:
    - meta_cell: GeoDataFrame of cell metadata.
    - cat: Column name in meta_cell containing the cluster labels.
    - alphas: List of alpha values to compute shapes for.

    Returns:
    - GeoDataFrame of alpha shapes.

    """

    gdf_alpha = gpd.GeoDataFrame()

    for inv_alpha in alphas:

        for inst_cluster in meta_cell[cat].unique():

            inst_clust = meta_cell[meta_cell[cat] == inst_cluster]

            if inst_clust.shape[0]> 3:

                nested_array = inst_clust['geometry'].values

                # Convert to a 2D NumPy array
                flat_array = np.vstack(nested_array)

                inst_shape = alpha_shape(flat_array, inv_alpha)

                inst_name = inst_cluster + '_' + str(inv_alpha)

                gdf_alpha.loc[inst_name, 'name'] = inst_name

                gdf_alpha.loc[inst_name, 'cat'] = inst_cluster

                gdf_alpha.loc[inst_name, 'geometry'] = inst_shape

                gdf_alpha.loc[inst_name, 'inv_alpha'] = int(inv_alpha)

    gdf_alpha["geometry"] = gdf_alpha["geometry"].apply(lambda geom: _round_coordinates(geom, precision=2))

    gdf_alpha['area'] = gdf_alpha.area

    gdf_alpha = gdf_alpha.loc[gdf_alpha.area.sort_values(ascending=False).index.tolist()]

    return gdf_alpha

def alpha_shape_geojson(gdf_alpha, meta_cluster, inst_alpha):

    geojson_alpha = json.loads(gdf_alpha.to_json())

    # Step 2: Edit the properties of each feature
    for feature in geojson_alpha["features"]:

        if feature['geometry'] is not None:

            # Parse the geometry with Shapely for additional calculations
            geometry = shape(feature["geometry"])

            # Add area property
            feature["properties"]["area"] = geometry.area

            id = feature['id']

            color = meta_cluster.loc[id.split('_')[0], 'color']

            # Add a custom color property (example: based on the area)
            feature["properties"]["color"] = color # [255, 0, 0, 100]  # RGBA values
        else:
            # print('is None')
            pass

    geojson_alpha['inst_alpha'] = inst_alpha

    return geojson_alpha

def create_hextile(radius, path_landscape_files=None, img_height=100, img_width=100, pixel_size=0.2125):

    if isinstance(path_landscape_files, str):
        tree = ET.parse(os.path.join(path_landscape_files, "pyramid_images/bound.dzi"))
        root = tree.getroot()
        img_width = int(root[0].attrib["Width"])
        img_height = int(root[0].attrib["Height"])

        transformation_matrix = pd.read_csv(
            f"{path_landscape_files}/micron_to_image_transform.csv", sep=" ", header=None
        ).values[:3, :3]

    else:
        transformation_matrix = np.eye(3)

    hex_height = 2 * radius
    hex_width = np.sqrt(3) * radius
    vert_spacing = 3 / 4 * hex_height  # = 1.5 * r for pointy-topped hexagons
    horiz_spacing = hex_width

    # Calculate number of hexes
    n_cols = int(np.ceil(img_width / horiz_spacing)) + 2
    n_rows = int(np.ceil(img_height / vert_spacing)) + 2

    # Precompute unit hexagon
    angles = np.radians(np.arange(0, 360, 60))
    unit_hex = Polygon([(radius * np.sin(a), radius * np.cos(a)) for a in angles])

    # Generate hexagons by translating the unit hex
    hexagons = []
    for row in range(n_rows):
        for col in range(n_cols):
            x = col * horiz_spacing
            y = row * vert_spacing
            if row % 2 == 1:
                x += horiz_spacing / 2
            hexagons.append(translate(unit_hex, xoff=x, yoff=y))

    # Define image boundary as a shapely box (left, bottom, right, top)
    image_bounds = box(0, 0, img_width, img_height)

    # Clip each hexagon to this box
    clipped_hexes = [
        hex.intersection(image_bounds)
        for hex in hexagons
        if hex.intersects(image_bounds)
    ]

    # Replace original GeoDataFrame
    gdf_hextile = gpd.GeoDataFrame(geometry=clipped_hexes)

    gdf_hextile.rename(columns={"geometry": "geometry_image_space"}, inplace=True)
    gdf_hextile.set_geometry("geometry_image_space", inplace=True)

    transformation_matrix_inv = np.linalg.inv(transformation_matrix)

    a = transformation_matrix_inv[0, 0]
    b = transformation_matrix_inv[0, 1]
    d = transformation_matrix_inv[1, 0]
    e = transformation_matrix_inv[1, 1]
    xoff = transformation_matrix_inv[0, 2]
    yoff = transformation_matrix_inv[1, 2]

    inverse_affine_params = [a, b, d, e, xoff, yoff]

    gdf_hextile['geometry'] = gdf_hextile['geometry_image_space'].apply(
    lambda geom: affine_transform(geom, inverse_affine_params)
    )

    gdf_hextile.set_geometry("geometry", inplace=True)

    radius_in_microns = pixel_size * radius

    if isinstance(path_landscape_files, str):
        gdf_hextile.to_parquet(os.path.join(path_landscape_files, "hextiles.parquet"))
        print(f"Hextiles saved at '{path_landscape_files}' as 'hextiles.parquet'\n")

        fig, ax = plt.subplots(1, 1, figsize=(60, 80))
        gdf_hextile.plot(ax=ax, alpha=1, linewidth=1, facecolor='none', edgecolor='black')
        ax.set_title(f"Hextiles (hexagon radius: {radius_in_microns} microns)", fontsize=50)
        ax.set_xlabel("x (pixels)", fontsize=25)
        ax.set_ylabel("y (pixels)", fontsize=25)
        plt.xticks(fontsize=20)
        plt.yticks(fontsize=20)
        plt.gca().invert_yaxis()
        plt.show()
        plt.close()

    return gdf_hextile


def calc_nbg_cd(
    adata,
    gdf_nbhd: gpd.GeoDataFrame,
    cd_mode: str = 'CD/LCD',
    unique_nbhd_col: str = "name"
) -> gpd.GeoDataFrame:
    """
    Calculate the mean expression of cells within a neighborhood (CD)
    or the mean expression of cells from a given Leiden cluster (LCD).

    Parameters
    ----------
    adata : AnnData
        AnnData object with spatial coordinates in `.obsm['spatial']`,
        gene expression in `.X`, and clustering in `adata.obs['leiden']`.

    gdf_nbhd : GeoDataFrame
        GeoDataFrame of neighborhood polygons, containing at least one unique ID column.

    cd_mode : str, default "CD/LCD"
        Mode of calculation: "CD" (all cells) or "LCD" (per cluster).

    unique_nbhd_col : str, default "name"
        Name of the column in `gdf_nbhd` that uniquely identifies each neighborhood.

    Returns
    -------
    GeoDataFrame
        GeoDataFrame with neighborhood geometries and mean gene expression values per gene.
        In LCD mode, returns data for the last cluster only (can be modified to return all).
    """
    gene_list = adata.var.index

    gene_exp = pd.DataFrame(
        adata.X.toarray() if hasattr(adata.X, 'toarray') else adata.X,
        columns=gene_list,
        index=adata.obs_names
    )

    gdf_cell = gpd.GeoDataFrame(
        data={'cluster': adata.obs['leiden'], **gene_exp},
        geometry=gpd.points_from_xy(*adata.obsm['spatial'].T[:2]),
        crs="EPSG:4326"
    )

    def compute_cd(gdf_cell_subset):
        joined = gdf_cell_subset.sjoin(gdf_nbhd[[unique_nbhd_col, 'geometry']], how="left", predicate="within")
        joined.drop(columns=['index_right', 'cat', 'geometry'], inplace=True, errors='ignore')

        df_nbhd_join = gdf_nbhd[[unique_nbhd_col]]
        for gene in gene_list:
            avg = joined.groupby(unique_nbhd_col)[gene].mean().reset_index()
            avg.columns = [unique_nbhd_col, gene]
            df_nbhd_join = df_nbhd_join.merge(avg, on=unique_nbhd_col, how='left')

        df_nbhd_join.rename(columns={unique_nbhd_col: 'nbhd_id'}, inplace=True)
        df_nbhd_join.set_index('nbhd_id', inplace=True)

        return df_nbhd_join

    if cd_mode == 'LCD':
        print ('Calculating NBG-LCD')
        nbhd_by_cluster = {}
        for cluster in gdf_cell['cluster'].unique():
            cluster_cells = gdf_cell[gdf_cell['cluster'] == cluster]
            nbhd_by_cluster[cluster] = compute_cd(cluster_cells)
        return nbhd_by_cluster

    elif cd_mode == 'CD':
        print ('Calculating NBG-CD')
        return compute_cd(gdf_cell)

    else:
        raise ValueError("cd_mode must be 'CD' or 'LCD'")


def generate_hex_grid(gdf_cell, radius=20):
    """
    Generate a hexagonal grid over the convex hull of a GeoDataFrame using affine translation.
    """
    # 1. Get the convex hull of all points
    bounding_geom = gdf_cell.unary_union.convex_hull
    minx, miny, maxx, maxy = bounding_geom.bounds

    # 2. Calculate spacing
    dx = np.sqrt(3) * radius  # horizontal spacing between centers
    dy = 1.5 * radius         # vertical spacing

    # 3. Create a unit hexagon centered at (0, 0)
    angles_deg = [30 + i * 60 for i in range(6)]
    angles_rad = [np.radians(a) for a in angles_deg]
    unit_hex = Polygon([(radius * np.cos(a), radius * np.sin(a)) for a in angles_rad])

    # 4. Estimate grid size
    n_cols = int((maxx - minx) / dx) + 3  # buffer for edge coverage
    n_rows = int((maxy - miny) / dy) + 3

    # 5. Translate the unit hex to form the grid
    hexagons = []
    for row in range(n_rows):
        for col in range(n_cols):
            x = col * dx
            y = row * dy
            if row % 2 == 1:
                x += dx / 2
            hex = translate(unit_hex, xoff=x + minx - dx, yoff=y + miny - dy)
            if hex.intersects(bounding_geom):
                hexagons.append(hex)

    return gpd.GeoDataFrame({
        'name': [f'hex_{i}' for i in range(len(hexagons))],
        'geometry': hexagons
    }, crs=gdf_cell.crs)


def calc_grad_nbhd_from_roi(polygon, gdf_reference, band_width=300):
    """
    Generate concentric rings (neighborhood bands) from a polygon,
    clipped to the convex hull of a reference GeoDataFrame.
    
    Parameters:
    -----------
    polygon : GeoDataFrame
        GeoDataFrame containing a single polygon
    gdf_reference : GeoDataFrame
        Reference GeoDataFrame used to calculate the boundary area (convex hull)
    band_width : float
        Width of each band in microns (default: 300)
    
    Returns:
    --------
    GeoDataFrame
        GeoDataFrame with columns for band (index of ring) and geometry (polygon)
    """
    if len(polygon) != 1:
        raise ValueError("Input polygon GeoDataFrame must contain exactly one polygon")
    
    roi_polygon = polygon.geometry.iloc[0]
    boundary = gdf_reference.unary_union.convex_hull

    bands = []
    current_polygon = roi_polygon
    band_idx = 0

    # Add the original polygon as band 0
    bands.append({'band': 'grad_'+ str(band_idx), 'geometry': roi_polygon})

    while True:
        band_idx += 1
        # Generate next ring
        next_buffer = current_polygon.buffer(band_width)
        ring = next_buffer.difference(current_polygon)

        # Clip the ring to the convex hull boundary
        ring_clipped = ring.intersection(boundary)

        # Stop if no part of the ring remains within boundary
        if ring_clipped.is_empty:
            break

        bands.append({'band': 'grad_'+ str(band_idx), 'geometry': ring_clipped})
        current_polygon = next_buffer

    gdf = gpd.GeoDataFrame(bands, crs=polygon.crs)
    gdf['band_width'] = band_width

    return gdf


def calc_nbg_cf(data_dir, gdf_nbhd, unique_nbhd_col='name'):
    """
    Calculates the neighborhood by gene expression.

    Parameters
    ----------
    data_dir : str
        Path to the directory containing the 'transcripts.parquet' file. The file must contain the 
        columns: 'feature_name', 'x_location', 'y_location', and 'cell_id'.

    gdf_nbhd : geopandas.GeoDataFrame
        GeoDataFrame of neighborhoods. Must include geometries and a column with unique neighborhood 
        identifiers (default column name is 'name').

    unique_nbhd_col : str, optional
        Name of the column in `gdf_nbhd` that uniquely identifies each neighborhood (default is 'name').

    Returns
    -------
    geopandas.GeoDataFrame
        A GeoDataFrame where each row corresponds to a neighborhood, with columns representing the count 
        of each transcript feature. Includes geometry for each neighborhood.

    """
    print ('Calculating NBG-CF')
    # Load only needed columns from the transcript data
    df_trx = pd.read_parquet(
        f'{data_dir}/transcripts.parquet',
        columns=['feature_name', 'x_location', 'y_location', 'cell_id'],
        engine='pyarrow'
    )

    # Convert to GeoDataFrame
    geometry = gpd.points_from_xy(df_trx['x_location'], df_trx['y_location'])
    gdf_trx = gpd.GeoDataFrame(df_trx[['feature_name']], geometry=geometry, crs="EPSG:4326")

    # Spatial join: assign transcripts to neighborhoods
    gdf_trx = gdf_trx.sjoin(gdf_nbhd[[unique_nbhd_col, 'geometry']], how="left", predicate="within")
    gdf_trx.rename(columns={unique_nbhd_col: 'nbhd_id'}, inplace=True)

    # Count feature occurrences per neighborhood
    df_counts = gdf_trx.groupby(['nbhd_id', 'feature_name']).size().unstack(fill_value=0)
    df_counts = df_counts.rename_axis("nbhd_id").rename_axis(None, axis=1)

    return df_counts

class NBHD:
    """A class representing neighborhoods with associated derived data matrices."""
    
    def __init__(
            self,
            gdf,
            nbhd_type,
            adata,
            data_dir,
            path_landscape_files, 
            source=None,
            name=None,
            meta=None
            ):
        """
        Initialize a neighborhood object.

        Parameters
        ----------
        gdf : geopandas.GeoDataFrame
            A GeoDataFrame with one row per neighborhood. Must have a 'geometry' column.
        nbhd_type : str
            One of: 'SKTCH', 'HEX', 'ALPH', 'GRAD'
        adata : Anndata that processed with spatialdata-io and spatialdata from raw Xenium output
        data_dir : str, path to the raw data directory
        path_landscape_files : str, path to the landscape files directory
        source : str or dict, optional
            Optional description of where this neighborhood set came from 
            (e.g., 'B cells', clustering params)
        name : str, optional
            A name or label for this neighborhood set.
        meta : dict, optional
            Any other user-defined metadata to store.
        """
        self.gdf = gdf.copy()
        self.nbhd_type = nbhd_type
        self.adata = adata
        self.data_dir = data_dir
        self.path_landscape_files = path_landscape_files
        self.source = source
        self.name = name
        self.meta = meta or {}

        # Store all derived high-dimensional data here
        self.derived = {
            'NBI': {},  # keyed by metric name: mean, median,
            'NBG-CF': None,
            'NBG-CD': None,
            'NBG-LCD': {},  # keyed by cluster name
            'NBP': {},  # keyed by abs/pct
            'NBN-O': None,
            'NBN-B': None,
        }

    def set_derived(self, key, subkey=None):
        """
        Set a derived data matrix.

        Parameters
        ----------
        key : str
            One of 'NBI', 'NBG-CF', 'NBG-CD', 'NBG-LCD', 'NBP', 'NBN-O', 'NBN-B', 'NBM'
        subkey : str, optional
            For NBG-LCD or other nested structures, store under a subkey 
            (e.g., cluster name).
        """

        if key == 'NBG-CD':
            data = calc_nbg_cd(self.adata, self.gdf,'CD')

        elif key == 'NBG-LCD':
            data = calc_nbg_cd(self.adata, self.gdf,'LCD')

        elif key == 'NBG-CF':
            data = calc_nbg_cf(self.data_dir, self.gdf)

        elif key == 'NBP':
                data = {}
                gdf_cell = _get_gdf_cell(self.adata)
                data['abs'], data['pct'] = calc_nbp(gdf_cell, self.gdf)

        elif key == 'NBM':
                gdf_trx = _get_gdf_trx(self.data_dir)
                gdf_cell = _get_gdf_cell(self.adata)
                data = get_nbhd_meta(self.gdf, 'name', gdf_trx, gdf_cell)

        elif key == 'NBN-O':
            if self.nbhd_type == 'ALPH':
                nb = self.gdf[['name','geometry']]
                print ('Calculating neighborhood overlap')
                data = calc_nb_overlap(nb)
            else:
                raise ValueError("NBN-O can be derived for ALPH only")
            
        elif key == 'NBN-B':
            if self.nbhd_type == 'ALPH':
                raise ValueError("NBN-B can not be derived for nbhd having overlap")
            else:
                nb = self.gdf[['name','geometry']]
                print ('Calculating neighborhood bordering')
                data = calc_nb_bordering(nb)

        if key == 'NBI':
            data = calc_nbg_cd(self.adata, self.gdf,'CD')

            # #### Calculate and attach NBI ####
            # Load the morphology image
            file_path = f"{self.data_dir}/morphology_focus/morphology_focus_0000.ome.tif"
            img = imread(file_path)

            # Convert gdf_nbhd to pixel space
            path_transformation_matrix = f'{self.path_landscape_files}/micron_to_image_transform.csv'

            transformation_matrix = pd.read_csv(
                path_transformation_matrix, header=None, sep=" "
            ).values

            gdf_nbhd_pixel = self.gdf.copy()
            gdf_nbhd_pixel["geometry"] = batch_transform_geometries(gdf_nbhd_pixel["geometry"], transformation_matrix, 1)

            # Extract zonal stats and attach
            data = {}
            channel_name_dict = {0:'dapi',1:'bound', 2:'rna', 3:'prot'}
            for metric in ['mean', 'median', 'std']:
                df_stats = calc_img_zonal_stats(gdf_nbhd_pixel, img, channel_names=channel_name_dict, stats_func=metric)
                df_stats.set_index('nbhd_id', inplace=True)
                data[metric] = df_stats

        if key in {'NBI','NBP', 'NBG-LCD'}:
            for subkey in data.keys():
                self.derived[key][subkey] = data[subkey]
        else:
            self.derived[key] = data

        print (f'{key} is derived and attached to nbhd' )

    def _add_geo(self, df):
        return (
            self.gdf[['name', 'geometry']]
            .set_index('name')
            .join(df, how='left')
            .fillna(0)
            .reset_index()
            .rename(columns={'name': 'nbhd_id'})
        )

    def get_derived(self, key, subkey=None):
        """Retrieve derived data by key and optional subkey."""
        if key in {'NBI','NBP', 'NBG-LCD'}:
            df = self.derived[key].get(subkey)
            return self._add_geo(df)
        df = self.derived.get(key)
        return self._add_geo(df)

    
    def to_geodataframe(self):
        """Return the underlying GeoDataFrame."""
        return self.gdf

    def summary(self):
        """Return a summary dictionary of the neighborhood properties."""
        return {
            "name": self.name,
            "type": self.nbhd_type,
            "n_regions": len(self.gdf),
            "derived": {k: self._derived_summary(k) for k in self.derived},
            "meta": self.meta,
        }

    def _derived_summary(self, key):
        """Internal method to summarize derived data shapes."""

        val = self.derived.get(key)

        # Skip if top-level key is unset
        if val is None:
            return None

        if key in ['NBI', 'NBP', 'NBG-LCD']:
            if key == 'NBI':
                subkeys = ['mean', 'median', 'std']
            elif key == 'NBP':
                subkeys = ['abs', 'pct']
            elif key == 'NBG-LCD':
                subkeys = sorted(self.adata.obs['leiden'].unique().tolist())

            summary = {}
            for subkey in subkeys:
                subval = val.get(subkey)
                summary[subkey] = subval.shape if hasattr(subval, "shape") else None
            return summary
        else:
            return val.shape if hasattr(val, "shape") else None
    

def calc_nbp(gdf_cell, gdf_nbhd, nbhd_col='name'):
    """
    Calculate cell counts and percentages per cluster within neighborhoods.
    
    Returns two GeoDataFrames:
    1. Raw counts per neighborhood-cluster combination
    2. Percentage distribution of clusters within each neighborhood
    
    Both retain original neighborhood geometries.
    """

    print ('Calculating NBP')
    # Validate inputs
    required = {'geometry', nbhd_col}
    if not required.issubset(gdf_nbhd.columns):
        raise ValueError(f"gdf_nbhd missing required columns: {required - set(gdf_nbhd.columns)}")
    if not {'geometry', 'cluster'}.issubset(gdf_cell.columns):
        raise ValueError("gdf_cell missing required 'geometry' or 'cluster' column")

    # Spatial join and count
    counts = (
        gdf_cell.sjoin(gdf_nbhd[[nbhd_col, 'geometry']], how='left', predicate='within')
        .groupby([nbhd_col, 'cluster'])
        .size()
        .unstack(fill_value=0)
        .pipe(lambda df: df.set_axis(df.columns.astype(str), axis=1))
    )
    
    # Calculate percentages
    percentages = counts.div(counts.sum(axis=1), axis=0).fillna(0) * 100
    
    return counts, percentages


def _get_gdf_trx(data_dir):
    """
    Load transcript data as a GeoDataFrame with spatial coordinates.
    """
    df_trx = pd.read_parquet(
        f'{data_dir}/transcripts.parquet',
        columns=['feature_name', 'x_location', 'y_location', 'cell_id'],
        engine='pyarrow'
    )
    geometry = gpd.points_from_xy(df_trx['x_location'], df_trx['y_location'])
    return gpd.GeoDataFrame(df_trx[['feature_name', 'cell_id']], geometry=geometry, crs="EPSG:4326")


def _get_gdf_cell(adata):
    """
    Load cell-level cluster and spatial coordinates from an h5ad file as a GeoDataFrame.
    """

    return gpd.GeoDataFrame(
        {'cluster': adata.obs['leiden']},
        geometry=gpd.points_from_xy(*adata.obsm['spatial'].T[:2]),
        crs="EPSG:4326"
    )


def _get_df_cell(adata):
    """
    Load cell-level cluster and spatial coordinates from an h5ad file as a DataFrame.
    """

    df_cell = pd.DataFrame({
        'cluster': adata.obs['leiden'],
        'x': adata.obsm['spatial'][:, 0],
        'y': adata.obsm['spatial'][:, 1],
        }
    )

    df_cell['geometry'] = df_cell.apply(lambda row: [round(row['x'],3), round(row['y'], 3)], axis=1)

    return df_cell


def get_nbhd_meta(gdf_nbhd, unique_nbhd_col, gdf_trx, gdf_cell):
    """
    Compute neighborhood-level summary statistics including transcript and cell assignments,
    along with area and perimeter from geometry.

    Parameters
    ----------
    gdf_nbhd : GeoDataFrame
        GeoDataFrame of neighborhoods with geometries and a unique identifier column.

    unique_nbhd_col : str
        Column name in `gdf_nbhd` that uniquely identifies each neighborhood (e.g., 'name').

    gdf_trx : GeoDataFrame
        GeoDataFrame of transcripts with 'cell_id' and point geometries.

    gdf_cell : GeoDataFrame
        GeoDataFrame of cells with point geometries.

    Returns
    -------
    DataFrame
        Summary DataFrame indexed by neighborhood ID, containing:
        - total_trx: total number of transcripts
        - unassigned_trx_count: count of 'UNASSIGNED' transcripts
        - assigned_trx_count: count of assigned transcripts
        - assigned_trx_pct: percent of assigned transcripts
        - unassigned_trx_pct: percent of unassigned transcripts
        - cell_count: number of cells in the neighborhood
        - area: area of each neighborhood geometry (in coordinate system units)
        - perimeter: perimeter (length) of each neighborhood polygon
    """

    print ('Calculating NBM')
    # Keep the index same as nbhd id or name
    gdf_nbhd = gdf_nbhd.set_index("name")
    gdf_nbhd["name"] = gdf_nbhd.index
    
    # Assign transcripts to neighborhoods
    gdf_trx = gdf_trx.sjoin(gdf_nbhd[[unique_nbhd_col, 'geometry']], how="left", predicate="within")

    # Aggregate transcript assignment stats
    summary = (
        gdf_trx.groupby(unique_nbhd_col)
        .agg(
            total_trx=("cell_id", "size"),
            unassigned_trx_count=("cell_id", lambda x: (x == "UNASSIGNED").sum()),
            assigned_trx_count=("cell_id", lambda x: (x != "UNASSIGNED").sum())
        )
    )
    summary["assigned_trx_pct"] = summary["assigned_trx_count"] / summary["total_trx"]
    summary["unassigned_trx_pct"] = summary["unassigned_trx_count"] / summary["total_trx"]

    # Count cells per neighborhood
    gdf_c = gdf_cell[['geometry']].sjoin(gdf_nbhd[[unique_nbhd_col, 'geometry']], how="left", predicate="within")
    cell_counts = gdf_c.groupby(unique_nbhd_col).size().rename("cell_count")
    summary = summary.join(cell_counts)

    # Compute area and perimeter
    geom_stats = gdf_nbhd.set_index(unique_nbhd_col)[['geometry']].copy()
    geom_stats["area_squm"] = geom_stats.geometry.area.round(2)
    geom_stats["perimeter_um"] = geom_stats.geometry.length.round(2)
    summary = summary.join(geom_stats[["area_squm", "perimeter_um"]])
    summary.index.name = 'nbhd_id'

    return summary


def calc_nb_overlap(gdf_nbhd):
    """
    Calculate the pairwise overlap between all neighborhoods, including overlap area and geometry.
    Skips intersections that are empty or have zero area.

    Parameters
    ----------
    gdf_nbhd : GeoDataFrame
        GeoDataFrame with a 'name' column and polygon geometries for neighborhoods.

    Returns
    -------
    GeoDataFrame
        GeoDataFrame with:
        - 'nbhd_1': Name of the first neighborhood
        - 'nbhd_2': Name of the second neighborhood
        - 'overlap_area': Area of the overlapping region (rounded to 2 decimals)
        - 'geometry': Geometry of the overlapping region
    """

    print ('Calculating NBN-O')
    gdf_nbhd = gdf_nbhd.copy()
    gdf_nbhd["geometry"] = gdf_nbhd["geometry"].buffer(0)  # Ensure valid geometry

    results = []
    for nb1, nb2 in combinations(gdf_nbhd["name"], 2):
        geom1 = gdf_nbhd.loc[gdf_nbhd["name"] == nb1, "geometry"].values[0]
        geom2 = gdf_nbhd.loc[gdf_nbhd["name"] == nb2, "geometry"].values[0]
        intersection = geom1.intersection(geom2)

        # Skip empty or zero-area geometries
        if not intersection.is_empty and intersection.area > 0:
            results.append({
                "nbhd_1": nb1,
                "nbhd_2": nb2,
                "overlap_area": round(intersection.area, 2),
                "geometry": intersection
            })

    if results:
        return gpd.GeoDataFrame(results, geometry="geometry", crs=gdf_nbhd.crs)
    else:
        return gpd.GeoDataFrame(columns=["nbhd_1", "nbhd_2", "overlap_area", "geometry"], geometry="geometry", crs=gdf_nbhd.crs)
    

def calc_nb_bordering(gdf_nbhd):
    """
    Identify pairs of neighborhoods that share a border (touch), using spatial indexing for efficiency.

    Parameters
    ----------
    gdf_nbhd : GeoDataFrame
        GeoDataFrame containing neighborhood geometries and a unique 'name' column.

    Returns
    -------
    DataFrame
        A DataFrame with columns: ['nbhd_1', 'nbhd_2'] representing neighborhoods that touch.
    """

    print ('Calculating NBN-B')
    gdf_nbhd = gdf_nbhd.copy()
    gdf_nbhd["geometry"] = gdf_nbhd["geometry"].buffer(0)  # Ensure valid geometry

    # Spatial join on self with 'touches' predicate
    gdf_touches = gpd.sjoin(gdf_nbhd, gdf_nbhd, how="inner", predicate="touches")

    # Filter out self-matches if they appear
    gdf_touches = gdf_touches[gdf_touches["name_left"] != gdf_touches["name_right"]]

    # Keep only unique pairs (e.g. A-B but not B-A)
    gdf_touches["pair"] = gdf_touches.apply(lambda row: tuple(sorted((row["name_left"], row["name_right"]))), axis=1)
    gdf_touches = gdf_touches.drop_duplicates(subset="pair")

    return gdf_touches[["name_left", "name_right"]].rename(columns={"name_left": "nbhd_1", "name_right": "nbhd_2"}).reset_index(drop=True)


def calc_img_zonal_stats(
    polygon_src, 
    img, 
    unique_polygon_col_name='name', 
    channel_names=None,
    stats_func='mean',
):
    """
    Calculate zonal statistics for each polygon from a multi-channel image.

    Parameters:
    - polygon_src: Either:
        - GeoDataFrame containing polygon geometries and a unique identifier column
        - 2D NumPy array mask where each unique value represents a different polygon
    - img: 3D NumPy array (H, W, C) representing the multi-channel image.
    - unique_polygon_col_name: Column name in GeoDataFrame containing unique polygon identifiers.
                              Only used when polygon_src is a GeoDataFrame.
    - channel_names: dict mapping channel indices to channel names (e.g., {0: 'dapi', 1: 'bound', ...}).
    - stats_func: String, function, or list of strings/functions specifying statistics to calculate.
                 Options: 'mean', 'median', 'std', 'min', 'max', 'sum', 'count', 'percentile_<q>',
                 or any numpy function that takes an array and returns a scalar.
                 Default: 'mean'.
    - stats_func_names: Optional names for the statistics when using custom functions.
                       Should match length of stats_func if provided.

    Returns:
    - DataFrame with statistics per polygon per channel.
    """

    print (f'Calculating zontal stats...{stats_func}')
    # Standard statistics mapping
    STATS_FUNCS = {
        'mean': np.nanmean,
        'median': np.nanmedian,
        'std': np.nanstd,
        'min': np.nanmin,
        'max': np.nanmax,
        'sum': np.nansum,
        'count': lambda x: np.sum(~np.isnan(x)),
    }

    # Process stats_func argument
    if isinstance(stats_func, (str, callable)):
        stats_func = [stats_func]
    
    # Convert string stats to functions and validate
    stat_funcs = []
    stat_names = []
    
    for i, stat in enumerate(stats_func):
        if isinstance(stat, str):
            # Handle percentile case
            if stat.startswith('percentile_'):
                try:
                    q = float(stat.split('_')[1])
                    stat_funcs.append(lambda x, q=q: np.nanpercentile(x, q))
                    stat_names.append(f'p{q}')
                except (IndexError, ValueError):
                    raise ValueError(f"Invalid percentile specification: {stat}")
            else:
                if stat not in STATS_FUNCS:
                    raise ValueError(f"Unknown statistic: {stat}. Available: {list(STATS_FUNCS.keys())}")
                stat_funcs.append(STATS_FUNCS[stat])
                stat_names.append(stat)
        elif callable(stat):
            stat_funcs.append(stat)
            stat_names.append(name)
        else:
            raise ValueError("stats_func must be string, function, or list of these")

    height, width, num_channels = img.shape
    transform = rasterio.transform.from_origin(0, height, 1, 1)  # Dummy affine transform
    
    stats = []

    if isinstance(polygon_src, gpd.GeoDataFrame):
        # Process as GeoDataFrame
        for idx, row in polygon_src.iterrows():
            polygon = row.geometry
            polygon_name = row[unique_polygon_col_name]

            # Rasterize the polygon to create a mask
            mask = rasterize(
                [(mapping(polygon), 1)],
                out_shape=(height, width),
                transform=transform,
                fill=0,
                all_touched=True,
                dtype=np.uint8
            )

            # Calculate statistics per channel within the masked area
            polygon_stats = {'nbhd_id': polygon_name}
            
            for ch in range(num_channels):
                masked_data = img[:, :, ch][mask == 1]
                ch_name = channel_names.get(ch, f'channel_{ch}') if channel_names else f'channel_{ch}'
                
                for func, name in zip(stat_funcs, stat_names):
                    stat_value = func(masked_data) if masked_data.size > 0 else np.nan
                    polygon_stats[f'{ch_name}'] = stat_value

            stats.append(polygon_stats)
    else:
        # Process as numpy array mask
        unique_polygon_ids = np.unique(polygon_src)
        unique_polygon_ids = unique_polygon_ids[unique_polygon_ids != 0]  # Exclude background (0)
        
        for polygon_id in unique_polygon_ids:
            mask = (polygon_src == polygon_id)
            
            # Calculate statistics per channel within the masked area
            polygon_stats = {'nbhd_id': polygon_id}
            
            for ch in range(num_channels):
                masked_data = img[:, :, ch][mask]
                ch_name = channel_names.get(ch, f'channel_{ch}') if channel_names else f'channel_{ch}'
                
                for func, name in zip(stat_funcs, stat_names):
                    stat_value = func(masked_data) if masked_data.size > 0 else np.nan
                    polygon_stats[f'{ch_name}'] = stat_value

            stats.append(polygon_stats)

    return pd.DataFrame(stats)