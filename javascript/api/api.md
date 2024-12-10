# Celldega JavaScript API Documentation

The JavaScript component of Celldega is used within the Jupyter Widgets framework to provide interactive visualization in the context of a Jupyter notebook but can also be used as a standalone JavaScript library.


## `landscape_ist` API Documentation

The `landscape_ist` function initializes and renders an interactive spatial transcriptomics (IST) landscape visualization. This API is designed to work with Deck.gl and includes customizable visualization options, dynamic data updates, and UI interactions.

### Parameters

- **`el`** (`HTMLElement`): The root DOM element where the visualization is rendered.
- **`ini_model`** (`Object`): The initial data model containing configuration and state.
- **`token`** (`string`): Authentication token for accessing data.
- **`ini_x`, `ini_y`, `ini_z`** (`number`): Initial spatial coordinates for the view.
- **`ini_zoom`** (`number`): Initial zoom level for the visualization.
- **`base_url`** (`string`): Base URL for accessing data files.
- **`dataset_name`** (`string`, optional): Name of the dataset being visualized.
- **`trx_radius`** (`number`, optional): Initial radius for transcript points. Default: `0.25`.
- **`width`** (`number|string`, optional): Width of the visualization. Default: `100%`.
- **`height`** (`number`, optional): Height of the visualization. Default: `800`.
- **`view_change_custom_callback`** (`Function`, optional): Custom callback triggered on view changes.

---

### Public API

The `landscape_ist` function returns an object (`landscape`) with several methods for interacting with the visualization.

#### `update_matrix_gene`

Updates the visualization to highlight data for a specific gene.

##### Parameters
- **`inst_gene`** (`string`): The gene to highlight.

##### Behavior
- Updates the transcript layer to show data for the specified gene.
- Scrolls the bar graph to bring the selected gene into view.
- Toggles visibility of image layers and controls based on the selected gene.

---

#### `update_matrix_col`

Updates the visualization to highlight data for a specific column (e.g., cluster).

##### Parameters
- **`inst_col`** (`string`): The column to highlight.

##### Behavior
- Highlights the bar graph corresponding to the selected column.
- Updates cell and path layers to reflect the selected column.
- Toggles visibility of layers based on the column selection.

---

#### `update_matrix_dendro_col`

Updates the visualization based on a dendrogram selection of columns.

##### Parameters
- **`selected_cols`** (`Array<string>`): The list of selected column names.

##### Behavior
- Highlights the selected columns in the bar graph.
- Updates layers to reflect the selection.

---

#### `update_view_state`

Updates the view state of the Deck.gl visualization.

##### Parameters
- **`new_view_state`** (`Object`): The new view state configuration.
- **`close_up`** (`boolean`): Whether the view should zoom in closely.
- **`trx_layer`** (`Object`): The transcript layer to update.

##### Behavior
- Adjusts the viewport and reconfigures layers based on the new view state.

---

#### `update_layers`

Updates all visualization layers.

##### Behavior
- Refreshes the Deck.gl layers with the current visualization state.

---

#### `finalize`

Finalizes the Deck.gl instance and cleans up resources.

##### Behavior
- Disposes of all Deck.gl resources and event listeners to prevent memory leaks.

---

### Usage Example

```

javascript
import { landscape_ist } from 'path/to/landscape_ist';

const rootElement = document.getElementById('visualization-container');
const model = { /* Model containing visualization data */ };

const visualization = await landscape_ist(
    rootElement,
    model,
    'example-token',
    100,
    200,
    0,
    -5,
    'https://example.com/data',
    'Example Dataset'
);

// Update the visualization with a specific gene.
visualization.update_matrix_gene('TP53');

// Update the visualization with a specific column.
visualization.update_matrix_col('Cluster 1');

// Finalize the visualization when done.
visualization.finalize();

```

---

## `matrix_viz` API Documentation

The `matrix_viz` function initializes and renders a matrix visualization. This API is built using approaches and code adaptations from the Clustergrammer-GL library, and it integrates tightly with Deck.gl to provide interactive and dynamic visualizations.

### Parameters

- **`model`** (`Object`): The model object containing configuration data for the visualization.
- **`el`** (`HTMLElement`): The root DOM element where the visualization is rendered.
- **`network`** (`Object`): The network object containing the matrix data to visualize.
- **`width`** (`string|number`, optional): The width of the visualization. Default: `'800'`.
- **`height`** (`string|number`, optional): The height of the visualization. Default: `'800'`.
- **`row_label_callback`** (`Function`, optional): A callback function triggered on row label interactions.
- **`col_label_callback`** (`Function`, optional): A callback function triggered on column label interactions.
- **`col_dendro_callback`** (`Function`, optional): A callback function triggered on dendrogram column interactions.

---

### Internal Behavior

The function performs the following setup:
1. **Deck.gl Integration**:
   - Initializes a Deck.gl instance for the matrix visualization.
   - Sets properties for interactivity, including tooltips, view state changes, and layer filtering.

2. **Matrix Data Setup**:
   - Parses and structures the matrix data from the `network` object.
   - Configures labels, categories, and dendrograms for both rows and columns.

3. **Layer Initialization**:
   - Creates layers for:
     - Matrix cells.
     - Row and column labels.
     - Row and column categories.
     - Row and column dendrograms.
   - Attaches interactions (e.g., click events) to these layers.

4. **UI Setup**:
   - Creates a container for the visualization and appends it to the root DOM element.


---

### Example Usage

```javascript
import { matrix_viz } from 'path/to/matrix_viz';

const rootElement = document.getElementById('matrix-container');
const model = { /* Model containing visualization data */ };
const network = { /* Network object representing the matrix data */ };

// Callback functions
const rowLabelCallback = (row) => {
    console.log('Row label clicked:', row);
};

const colLabelCallback = (col) => {
    console.log('Column label clicked:', col);
};

const colDendroCallback = (dendro) => {
    console.log('Column dendrogram clicked:', dendro);
};

// Initialize the matrix visualization
await matrix_viz(
    model,
    rootElement,
    network,
    800,
    800,
    rowLabelCallback,
    colLabelCallback,
    colDendroCallback
);
```