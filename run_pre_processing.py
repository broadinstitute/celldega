import os
import argparse
import celldega as dega

def main(sample, data_root_dir, tile_size, path_landscape_files):
    """
    Main function to preprocess Xenium data and generate landscape files.

    Args:
        sample (str): Name of the sample (e.g., 'Xenium_V1_human_Pancreas_FFPE_outs').
        data_root_dir (str): Root directory containing the sample data.
        tile_size (int): Size of the tiles for transcript and boundary tiles.
        path_landscape_files (str): Directory to save the landscape files.

    Example:
        change directory to celldega, and run:

        python run_pre_processing.py \
            --sample Xenium_V1_human_Pancreas_FFPE_outs \
            --data_root_dir data \
            --tile_size 250 \
            --path_landscape_files notebooks/Xenium_V1_human_Pancreas_FFPE_outs

    """
    print(f"Starting preprocessing for sample: {sample}")

    # Construct data directory
    data_dir = os.path.join(data_root_dir, sample)

    # Create necessary directories if they don't exist
    for folder in [data_dir, path_landscape_files]:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"Created directory: {folder}")

    # Determine technology based on the presence of experiment.xenium file
    if os.path.exists(os.path.join(data_dir, 'experiment.xenium')):
        technology = 'Xenium'
    else:
        raise ValueError("Unsupported technology. Only Xenium is supported in this script.")

    # Unzip compressed files in Xenium data folder
    print("Unzipping compressed files...")
    dega.pre._xenium_unzipper(data_dir)

    # Check required files for preprocessing
    print("Checking required files...")
    dega.pre._check_required_files(technology, data_dir)

    # Calculate and save CBG gene parquet files
    print("Calculating and saving CBG gene parquet files...")
    cbg = dega.pre.read_cbg_mtx(os.path.join(data_dir, 'cell_feature_matrix'))
    dega.pre.save_cbg_gene_parquets(path_landscape_files, cbg, verbose=True)

    # Make meta gene files
    print("Creating meta gene files...")
    path_cbg = os.path.join(data_dir, 'cell_feature_matrix')
    path_output = os.path.join(path_landscape_files, 'meta_gene.parquet')
    dega.pre.make_meta_gene(technology, path_cbg, path_output)

    # Write transform file
    print("Writing transformation matrix...")
    transformation_matrix = dega.pre.write_xenium_transform(data_dir, path_landscape_files)

    # Make cell image coordinates
    print("Creating cell image coordinates...")
    path_transformation_matrix = os.path.join(path_landscape_files, 'xenium_transform.csv')
    path_meta_cell_micron = os.path.join(data_dir, 'cells.csv.gz')
    path_meta_cell_image = os.path.join(path_landscape_files, 'cell_metadata.parquet')
    dega.pre.make_meta_cell_image_coord(
        technology, 
        path_transformation_matrix, 
        path_meta_cell_micron, 
        path_meta_cell_image, 
        image_scale=1
    )

    # Create cluster and meta cluster files
    print("Creating cluster and meta cluster files...")
    clusters = dega.pre.create_cluster_and_meta_cluster(technology, data_dir, path_landscape_files)

    # Generate transcript tiles
    print("Generating transcript tiles...")
    path_trx = os.path.join(data_dir, 'transcripts.parquet')
    path_trx_tiles = os.path.join(path_landscape_files, 'transcript_tiles')
    print(f"Generating transcript tiles for {data_dir} and saving at {path_trx_tiles}")
    tile_bounds = dega.pre.make_trx_tiles(
        technology,
        path_trx,
        path_transformation_matrix,
        path_trx_tiles,
        coarse_tile_factor=10,
        tile_size=tile_size,
        chunk_size=100000,
        verbose=False,
        image_scale=1,
        max_workers=2
    )

    # Generate boundary tiles
    print("Generating boundary tiles...")
    path_cell_boundaries = os.path.join(data_dir, 'cell_boundaries.parquet')
    path_output = os.path.join(path_landscape_files, 'cell_segmentation')
    print(f"Generating boundary tiles for {data_dir} and saving at {path_output}")
    cells_orig = dega.pre.make_cell_boundary_tiles(
        technology,
        path_cell_boundaries,
        path_meta_cell_micron,
        path_transformation_matrix,
        path_output,
        coarse_tile_factor=10,
        tile_size=tile_size,
        tile_bounds=tile_bounds,
        image_scale=1,
        max_workers=2
    )

    # Create cluster-based gene expression
    print("Calculating cluster-based gene expression...")
    df_sig = dega.pre.cluster_gene_expression(technology, data_dir, path_landscape_files, cbg)

    # Save landscape parameters
    print("Saving landscape parameters...")
    image_info = [
        {
            "name": "dapi",
            "button_name": "DAPI",
            "color": [0, 0, 255]
        }
    ]
    dega.pre.save_landscape_parameters(
        technology, 
        path_landscape_files,
        'dapi_files',
        tile_size=tile_size,
        image_info=image_info,
        image_format='.webp'
    )

    print("Preprocessing completed successfully.")

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Preprocess Xenium data and generate landscape files.")
    parser.add_argument("--sample", required=True, help="Name of the sample (e.g., 'Xenium_V1_human_Pancreas_FFPE_outs').")
    parser.add_argument("--data_root_dir", required=True, help="Root directory containing the data for this sample and oher samples.")
    parser.add_argument("--tile_size", type=int, required=True, help="Size of the tiles for transcript and boundary tiles.")
    parser.add_argument("--path_landscape_files", required=True, help="Directory to save the landscape files.")

    # Parse arguments
    args = parser.parse_args()

    # Run the main function
    main(args.sample, args.data_root_dir, args.tile_size, args.path_landscape_files)