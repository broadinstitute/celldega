# Technologies
Celldega is utilizing a suite of complementary technologies to develop an efficient web-based spatial-omics visualization and analysis toolkit.

## Visualization Technologies
Spatial transcriptomics (ST) datasets tend to be very large and difficult for researchers to collaboratively analyze and visualize. Closely linking spatial- and data-visualizations to analysis is also key to extracting biological insights from these spatial data. We built the Celldega [`viz`](../python/viz/) module to help researchers interactively visualize large ST datasets within notebook-based workflows on the cloud (e.g., Terra.bio).

The Celldega [Landscape](../gallery) visualization method utilizes a novel vector tiling approach to enable interactive visualization of large ST datasets in a notebook environment or as a stand-alone webpage. This approach allows Celldega to visualize much larger datasets than current open-source tools - enabling interactive visualization of datasets with hundreds of millions of transcripts. We also utilize modern and efficient web image data formats ([WebP](#webp)) to reduce the data storage burden for interactive visualization. The corresponding [LandscapeFiles](../overview/file_formats.md) data format is compact enough to store on GitHub for the purposes of building a public gallery.

### Terra.bio
Terra.bio is a cloud-based compute and data storage platform that is being developed by the <a href='https://www.broadinstitute.org/spatial-technology-platform' target='_blank'>Broad Institute of MIT and Harvard</a>. We are utilizing Terra.bio to help <a href='https://www.broadinstitute.org/spatial-technology-platform' target='_blank'>Spatial Technology Platform</a> clients access, analyze, and visualize their ST data.

### Jupyter Widget
We utilize the Jupyter Widget ecosystem to build interactive spatial and data visualizations that enable users to perform two way communication between JavaScript (front-end) and Python (back-end). We are utilizing the <a href='https://anywidget.dev/' target='_blank'>AnyWidget</a> implementation to build our custom widgets.

### Deck.gl
Celldega uses the GPU-powered data visualization library <a href='https://deck.gl/' target='_blank'>deck.gl</a> to create high-performance spatial- and data-visualizations.

### Apache Parquet
Celldega uses the <a href='https://parquet.apache.org/' target='_blank'>Apache Parquet</a> file format for storing spatial data. This file format in combination with the JavaScript library [ParquetWASM](#parquetwasm-and-apache-arrow) and Apache Arrow in memory representation is used to build Celldega's high-performance vector tiling spatial visualization functionality (see <a href='https://observablehq.com/@kylebarron/geoarrow-and-geoparquet-in-deck-gl' target='_blank'>GeoArrow and GeoParquet in deck.gl</a>).

### ParquetWASM and Apache Arrow
ParquetWASM is a JavaScript library for reading Parquet files into Apache Arrow memory and utilizes Web Assembly (WASM) to run Rust in a browser environment. The Apache Arrow in-memory format is a complementary columnar in-memory format for storing data from Apache Parquet files. See <a href='https://observablehq.com/@kylebarron/geoarrow-and-geoparquet-in-deck-gl' target='_blank'>GeoArrow and GeoParquet in deck.gl</a> for more information.

### WebP

### DeepZoom

### Clustergrammer Visualization

## Data Analysis Technologies

### GeoPandas

### <a href='https://pysal.org/libpysal/' target='_blank'>LibPySal</a>: Python Spatial Analysis Library Core

### Clustergrammer Data Analysis
