# Celldega File Formats
While there has been tremendous progress in developing standardized data formats and architectures for spatial-omics data, namely [SpatialData](https://spatialdata.scverse.org/en/stable/) and the related [AnnData](https://anndata.readthedocs.io/en/stable/), these approaches currently lack support for interactive cloud-based visualization of large (>100M transcripts) Spatial Transcriptomics (ST) data. Furthermore, all-in-one data format approaches preclude the development of compact visualization-specific data formats.

The Celldega project addresses these challenges with the development of a new ST data format called LandscapeFiles, specifically built for cloud-based visualization. LandscapeFiles support Celldega's Landscape visualization method by leveraging compact [image formats](../technologies/index.md/#webp) and [cloud-native data formats](../technologies/index.md/#apache-parquet) to enable efficient storage and visualization of image (e.g., microscopy images) and vectorized data (e.g., transcript coordinates). This approach is highly scalable, enabling the visualization of very large ST datasets (>400M transcripts), while remaining compact enough that the  LandscapeFiles for an entire Xenium dataset can be hosted in a [public GitHub repository](https://github.com/broadinstitute/celldega_Xenium_Prime_Human_Skin_FFPE_outs/).


## LandscapeFiles
LandscapeFiles are generated using the Celldega [pre](../python/pre/api.md) module (see example Google Colab notebook [Celldega-Landscape-Pre-Process_Xenium-Pancreas-Dataset](https://colab.research.google.com/drive/1guUFhXP3nlZ4Es2-tsnraFKlAKHZSCZC?usp=sharing)) and are used by Celldega's JavaScript front-end to interactively visualize ST data. Users have several options for hosting LandscapeFiles both locally on the cloud (e.g., Terra.bio buckets) or locally (e.g., running a local server to locally host LandscapeFiles).

### iST LandscapeFiles

The file structure for a Xenium Prime dataset's LandscapeFiles is shown below.

```
.
├── cbg
├── cell_clusters
├── cell_metadata.parquet
├── cell_segmentation
├── df_sig.parquet
├── landscape_parameters.json
├── meta_gene.parquet
├── pyramid_images
│   ├── bound_files
│   ├── dapi_files
│   ├── prot_files
│   └── rna_files
│── transcript_tiles
└── xenium_transform.csv

```

The LandscapeFiles for an an example public 10X Genomics Xenium dataset can be found [here](https://github.com/broadinstitute/celldega_Xenium_Prime_Human_Skin_FFPE_outs).

#### Cell-by-Gene
The `cbg` directory contains parquet files for each gene. Each file has a table of all the non-zero single cell expression counts. See example below:

```
	A2ML1
aaaaljij-1	18
aaabgfcl-1	24
aaacghkb-1	28
aaachnfg-1	14
aaacknep-1	1

```

#### Cell Clusters
The `cell_clusters` directory contains single-cell clustering data. For Xenium data, these will include the default clustering results stored in two parquet files.

##### cluster.parquet
This file contains the cluster identity of each cell. See example below:

```
	cluster
aaaaljij-1	28
aaabgfcl-1	27
aaacghkb-1	27
aaachnfg-1	28
aaacknep-1	28

```

##### meta_cluster.parquet
This file contains metadata on the cell clusters, which includes the color and cell count. See example below:
```
	color	count
1	#1f77b4	12742
2	#ff7f0e	10058
3	#2ca02c	9171
4	#d62728	8781
5	#9467bd	7760

```

#### Cell Metadata
The `cell_metadata.parquet` file contains the centroid positions of all cells. See example below:

```
cell_id	name	geometry

aaaaljij-1	aaaaljij-1	[819.7626194690856, 10819.416697734863]
aaabgfcl-1	aaabgfcl-1	[861.7377139772034, 10683.254024123535]
aaacghkb-1	aaacghkb-1	[876.8403955191346, 10627.146491566895]
aaachnfg-1	aaachnfg-1	[799.6315031020813, 10692.094786328125]
aaacknep-1	aaacknep-1	[760.0623424668274, 10729.360408533203]

```

#### Cell Segmentation
The `cell_segmentation` directory contains tiled parquet files that contain cell segmentation polygons for the cells within a given tile. See example below:

```
cell_id	GEOMETRY	name

mnnojdjm-1	[[[35052.998290142576, 2648.999973659546], [35...	mnnojdjm-1
mnoafgkh-1	[[[35229.99735775, 2654.999800875], [35227.998...	mnoafgkh-1
mnodjmcf-1	[[[35090.99920641015, 2657.9998580948486], [35...	mnodjmcf-1
moelbbjj-1	[[[35233.997817008785, 2602.9998622198486], [3...	moelbbjj-1
moemfhce-1	[[[35242.998275892576, 2539.9998095], [35239.9...	moemfhce-1

```

#### Cell Cluster Gene Expression Signatures
The `df_sig.parquet` file contains the gene expression signatures of the cell clusters - defined as the average gene expression level of a cluster's cells. See example below:

```
	1	2	3	4	5	6	7	8	9	10	...	20	21	22	23	24	25	26	27	28	29
A2ML1	0.000235	0.000597	0.000109	0.000114	0.002320	0.000823	0.000996	0.000372	0.000760	0.000473	...	0.018356	0.0000	0.000000	0.000000	0.000000	0.000000	2.593168	8.309091	5.602632	0.000000
AAMP	0.296029	0.298668	0.032494	0.052727	0.003222	0.515027	0.014938	0.070061	0.395857	0.470894	...	0.122905	0.0960	0.429596	0.058206	0.128743	0.511224	0.580745	0.456566	0.136842	0.052632
AAR2	0.075655	0.069994	0.015375	0.023118	0.002964	0.118705	0.006971	0.038840	0.091410	0.117132	...	0.054270	0.0424	0.129148	0.022901	0.030938	0.130612	0.154244	0.117172	0.057895	0.021053
AARSD1	0.074557	0.156194	0.013412	0.017880	0.001546	0.200357	0.005477	0.028805	0.121057	0.120208	...	0.047087	0.0272	0.093274	0.019084	0.028942	0.223469	0.120083	0.024242	0.005263	0.010526
ABAT	0.004787	0.008053	0.009814	0.015830	0.000902	0.009743	0.004481	0.004832	0.003801	0.006626	...	0.008779	0.0072	0.004484	0.017176	0.008982	0.002041	0.006211	0.002020	0.000000	0.005263
```

#### Landscape Parameters
This file contains the configuration information about the dataset. See example below:

```
{
    "technology": "Xenium",
    "max_pyramid_zoom": 16,
    "tile_size": 250,
    "image_info": [
        {
            "name": "dapi",
            "button_name": "DAPI",
            "color": [
                0,
                0,
                255
            ]
        },
        {
            "name": "bound",
            "button_name": "BOUND",
            "color": [
                0,
                255,
                0
            ]
        },
        {
            "name": "rna",
            "button_name": "RNA",
            "color": [
                255,
                0,
                0
            ]
        },
        {
            "name": "prot",
            "button_name": "PROT",
            "color": [
                255,
                255,
                255
            ]
        }
    ],
    "image_format": ".webp"
}
```

#### Gene Metadata
The `gene_metadata.parquet` file contains gene level metadata including: average expression across all cells, standard deviation, max expression, proportion of cells with non-zero expression, and the color assigned to each gene. See example below:

```
	mean	std	max	non-zero	color
A2ML1	0.078391	3.128721	46.0	0.000009	#1f77b4
AAMP	0.175449	1.621841	7.0	0.000009	#ff7f0e
AAR2	0.048494	0.780702	4.0	0.000009	#2ca02c
AARSD1	0.060533	0.897824	4.0	0.000009	#d62728
ABAT	0.006575	0.285613	3.0	0.000009	#9467bd

```

#### Pyramid Images
The `pyramid_images` directory contains iST images from all available channels saved  [Deep Zoom pyramids](../technologies/index.md#deep-zoom) using the image file format [WebP](../technologies/index.md#webp). An example directory structure for a Xenium multi-modal dataset looks like:

```
.
├── bound.dzi
├── bound_files
│   ├── 0
│   ├── 1
│   ├── 10
│   ├── 11
│   ├── 12
│   ├── 13
│   ├── 14
│   ├── 15
│   ├── 16
│   ├── 2
│   ├── 3
│   ├── 4
│   ├── 5
│   ├── 6
│   ├── 7
│   ├── 8
│   ├── 9
│   └── vips-properties.xml
├── dapi.dzi
├── dapi_files
│   ├── 0
│   ├── 1
│   ├── 10
│   ├── 11
│   ├── 12
│   ├── 13
│   ├── 14
│   ├── 15
│   ├── 16
│   ├── 2
│   ├── 3
│   ├── 4
│   ├── 5
│   ├── 6
│   ├── 7
│   ├── 8
│   ├── 9
│   └── vips-properties.xml
├── prot.dzi
├── prot_files
│   ├── 0
│   ├── 1
│   ├── 10
│   ├── 11
│   ├── 12
│   ├── 13
│   ├── 14
│   ├── 15
│   ├── 16
│   ├── 2
│   ├── 3
│   ├── 4
│   ├── 5
│   ├── 6
│   ├── 7
│   ├── 8
│   ├── 9
│   └── vips-properties.xml
├── rna.dzi
└── rna_files
    ├── 0
    ├── 1
    ├── 10
    ├── 11
    ├── 12
    ├── 13
    ├── 14
    ├── 15
    ├── 16
    ├── 2
    ├── 3
    ├── 4
    ├── 5
    ├── 6
    ├── 7
    ├── 8
    ├── 9
    └── vips-properties.xml

```

#### Transcript Tiles

The `transcript_tiles` directory contains tiled parquet files that contain transcript data for transcripts within a given tile. See example below:

```
	name	geometry
20862147	AARSD1	[25663.38, 11758.09]
20862230	ABCA1	[25650.44, 11757.28]
20862780	ABCD1	[25634.19, 11754.12]
20862819	ABCD1	[25635.51, 11755.29]
20863051	ABHD6	[25506.54, 11753.75]

```

#### Image Transformation
The `xenium_transform.csv` file contains the 3x3 image transformation matrix to transition from physical coordinates into image coordinates.

### sST LandscapeFiles