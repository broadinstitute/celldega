# Technologies
Celldega utilizes a suite of complementary technologies to develop an efficient web-based spatial-omics analysis and visualization toolkit.

## Visualization Technologies
Spatial transcriptomics (ST) datasets can be very large and difficult for researchers to analyze and visualize collaboratively. Additionally, visualization that is linked to analysis is key to extracting biological insights. To address these issues, we built the Celldega [`viz`](../python/viz/) module to help researchers interactively visualize large ST datasets within notebook-based workflows on the cloud (e.g., Terra.bio).

The Celldega Landscape visualization method (see [Gallery](../gallery)) utilizes novel vector tiling approaches to enable interactive visualization of large ST datasets in a notebook environment or as a stand-alone webpage. This approach allows Celldega to visualize larger datasets than currently available open-source tools (e.g., datasets with hundreds of millions of transcripts). We also utilize modern web image data formats ([WebP](#webp)) to reduce the data storage burden for interactive visualization. The resulting [LandscapeFiles](../overview/file_formats.md#landscapefiles) data format serves as a compact and highly performant visualization-specific data format.

### Terra.bio
Terra.bio is a cloud-based compute and data storage platform that is being developed by the <a href='https://www.broadinstitute.org/spatial-technology-platform' target='_blank'>Broad Institute of MIT and Harvard</a>. We are utilizing Terra.bio to help <a href='https://www.broadinstitute.org/spatial-technology-platform' target='_blank'>Spatial Technology Platform</a> clients access, analyze, and visualize their ST data.

### Jupyter Widget
We utilize the Jupyter Widget ecosystem to build interactive spatial and data visualizations that enable users to perform two way communication between JavaScript (front-end) and Python (back-end). We are utilizing the <a href='https://anywidget.dev/' target='_blank'>AnyWidget</a> implementation to build our custom widgets.

### Deck.gl
Celldega uses the GPU-powered data visualization library <a href='https://deck.gl/' target='_blank'>deck.gl</a> to create high-performance spatial- and data-visualizations.

### Apache Parquet
Celldega uses the <a href='https://parquet.apache.org/' target='_blank'>Apache Parquet</a> file format for storing vectorized spatial data and metadata. This file format in combination with the JavaScript library [ParquetWASM](#parquetwasm-and-apache-arrow) and Apache Arrow in memory representation is used to build Celldega's high-performance vector tiling spatial visualization functionality (see <a href='https://observablehq.com/@kylebarron/geoarrow-and-geoparquet-in-deck-gl' target='_blank'>GeoArrow and GeoParquet in deck.gl</a>).

### ParquetWASM and Apache Arrow
ParquetWASM is a JavaScript library for reading Parquet files into Apache Arrow memory and utilizes Web Assembly (WASM) to run Rust in a browser environment. The Apache Arrow in-memory format is a columnar in-memory format that is used for storing data from Apache Parquet files and efficiently passing to deck.gl. For more information please see <a href='https://observablehq.com/@kylebarron/geoarrow-and-geoparquet-in-deck-gl' target='_blank'>GeoArrow and GeoParquet in deck.gl</a>.

### WebP
A modern image format developed by Google, offering efficient lossless compression and designed specifically for the web.

### Deep Zoom
We utilize the Deep Zoom image schema, developed by Microsoft, to enable efficient visualization of large multi-channel microscopy images. Deep Zoom tile images are stored using the WebP image format.

### Clustergrammer Visualization


## Data Analysis Technologies

### GeoPandas

### <a href='https://pysal.org/libpysal/' target='_blank'>LibPySal</a>: Python Spatial Analysis Library Core

### Clustergrammer Data Analysis
