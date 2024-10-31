def ist_segmentation_metrics(path_to_data, technology='Xenium'):

    """
        A function to calculate segmentation quality control
        metrics for imaging spatial transcriptomics data.
    """

    print('testing:', technology)

    # QC Metrics
    #

    # ...

    # Save these calculate metrics to a data structure (DataFrame)
    # dataset level (meta_dataset.parquet)
    # proportion of transcripts that are assigned to cells
    # total number of cells
    # average area of cells
    # average volume of cells (multiply by thickness)
    # average number of transcripts per cell
    # average number of genes per cell

    # gene leve (meta_gene.parquet)
    # average expression of each gene
    # proportion of cells expressing each gene
