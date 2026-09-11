/**
 * Presents a SpatialData store as the tables Celldega expects.
 *
 * This is the seam for the `adapt_dega` work: everything the viewer used to read from
 * `meta_gene.parquet`, `cell_metadata.parquet` and `cell_clusters/` is derived here from
 * `var`, `obs`, `obsm`, `uns` and expression arrays instead. Transcripts and boundaries
 * remain display Parquets. Native OME-Zarr images are handled by image_source.js.
 */

import * as arrow from 'apache-arrow';

import { geneStats, geneColumn, geneColumnSparse } from './csr';
import {
  defaultGeneColors,
  buildCellMetadataTable,
  buildClusterTable,
  buildMetaClusterTable,
  buildMetaGeneTable,
} from './dega_tables';
import { SpatialDataStore } from './spatialdata_store';

/**
 * `uns` key holding one hex colour per gene, in `var` order.
 *
 * This borrows Scanpy's categorical palette shape. The gene-specific key and var-order
 * alignment are profile conventions; AnnData does not realign this list on gene slicing.
 */
const GENE_COLORS_KEY = 'gene_colors';

/** Shown when the store has no clustering, matching what the profile writes today. */
const UNCLUSTERED = 'unclustered';

/** Map a Scanpy color list to categorical labels without sorting the labels. */
export const categoricalPalette = (categories, colors) =>
  Object.fromEntries(
    Array.from(categories, (name, i) => [String(name), colors[i]])
  );

export class SpatialDataAdapter {
  /**
   * @param {string} storeUrl - URL of the .zarr root
   * @param {object} [opts]
   * @param {string} [opts.table] - table name under `tables/`, defaults to "table"
   * @param {string} [opts.clusterColumn] - `obs` column to colour cells by
   * @param {string} [opts.centroidKey] - `obsm` key holding centroids, defaults to "spatial"
   * @param {string} [opts.transformElement] - element whose transform maps centroids into
   *   display space, e.g. "shapes/cell_boundaries". Without it centroids are used as-is,
   *   which for Xenium would leave them in microns while everything else is in pixels.
   * @param {string} [opts.coordinateSystem] - transform target, defaults to "global"
   */
  constructor(storeUrl, opts = {}) {
    this.store = new SpatialDataStore(storeUrl, { table: opts.table });
    this.clusterColumn = opts.clusterColumn ?? null;
    this.centroidKey = opts.centroidKey ?? 'spatial';
    this.transformElement = opts.transformElement ?? null;
    this.featureCatalog = opts.featureCatalog ?? null;
    this.coordinateSystem = opts.coordinateSystem ?? 'global';
    this._cache = new Map();
  }

  /**
   * Centroids in display space.
   *
   * `obsm["spatial"]` is in the element's own units -- microns for Xenium -- while
   * transcripts, boundaries and images are all in pixels. Skipping this would render cells
   * at 1/4.7 scale, in the corner of the image.
   */
  async _displayCentroids() {
    const centroids = await this.store.centroids(this.centroidKey);
    if (!this.transformElement) return centroids;

    const { scale, translation } = await this.store.elementTransform(
      this.transformElement,
      this.coordinateSystem
    );
    if (
      scale[0] === 1 &&
      scale[1] === 1 &&
      !translation[0] &&
      !translation[1]
    ) {
      return centroids;
    }

    const out = new Float64Array(centroids.length);
    for (let i = 0; i < centroids.length; i += 2) {
      out[i] = centroids[i] * scale[0] + translation[0];
      out[i + 1] = centroids[i + 1] * scale[1] + translation[1];
    }
    return out;
  }

  _once(key, fn) {
    if (!this._cache.has(key)) this._cache.set(key, fn());
    return this._cache.get(key);
  }

  /**
   * Stand-in for `meta_gene.parquet`.
   *
   * Uses precomputed var statistics when present. Otherwise it computes them from the
   * whole CSR X matrix, which requires downloading all matrix chunks.
   */
  async metaGeneTable() {
    return this._once('metaGene', async () => {
      const [genes, precomputed, colors] = await Promise.all([
        this.store.geneNames(),
        this.store.geneStatistics(),
        this.store.unsArray(GENE_COLORS_KEY),
      ]);

      // Statistics in `var` mean the gene list costs a few hundred KB. Without them the
      // whole matrix has to be read just to populate it, whatever its layout.
      const stats = precomputed ?? geneStats(await this.store.csr());

      // Controls (negative probes, unassigned codewords) are not in `var`, but they do
      // carry feature codes above every gene. Appending them keeps
      // `feature_code === row position`, which is what the transcript layer indexes.
      const extra = this.featureCatalog?.extra_features ?? [];
      const names = extra.length ? [...genes, ...extra] : genes;

      const pad = (values) => {
        if (!extra.length) return values;
        const out = new Float64Array(names.length);
        out.set(values.subarray(0, genes.length));
        return out;
      };

      // uns["gene_colors"] covers the genes only, but the list includes the controls. Passing
      // a short colour array would build an Arrow table with mismatched column lengths,
      // so the controls are filled from the same palette the reader uses when a store has
      // no colours at all.
      let geneColors = colors ? Array.from(colors, (c) => String(c)) : null;
      if (geneColors && geneColors.length < names.length) {
        const fallback = defaultGeneColors(names.length);
        geneColors = names.map((_, i) => geneColors[i] ?? fallback[i]);
      }

      return buildMetaGeneTable({
        names,
        mean: pad(stats.mean),
        std: pad(stats.std),
        max: pad(stats.max),
        nonZero: pad(stats.nonZero),
        colors: geneColors,
        isGene: names.map((_, i) => i < genes.length),
      });
    });
  }

  /** Stand-in for `cell_metadata.parquet`. */
  async cellMetadataTable() {
    return this._once('cellMetadata', async () => {
      const [names, centroids] = await Promise.all([
        this.store.cellNames(),
        this._displayCentroids(),
      ]);
      return buildCellMetadataTable({ names, centroids });
    });
  }

  /**
   * The `obs` column used for cluster colouring, as plain strings.
   * Falls back to a single group when no column is configured or it is missing.
   */
  async _clusterValues() {
    const cellNames = await this.store.cellNames();
    if (!this.clusterColumn) {
      return {
        cellNames,
        clusters: new Array(cellNames.length).fill(UNCLUSTERED),
      };
    }
    const raw = await this.store.obsColumn(this.clusterColumn);
    if (!raw) {
      return {
        cellNames,
        clusters: new Array(cellNames.length).fill(UNCLUSTERED),
      };
    }
    return {
      cellNames,
      clusters: Array.from(raw, (v) => (v == null ? 'N.A.' : String(v))),
    };
  }

  /** Stand-in for `cell_clusters/cluster.parquet`. */
  async clusterTable() {
    return this._once('cluster', async () => {
      const { cellNames, clusters } = await this._clusterValues();
      return buildClusterTable({ cellNames, clusters });
    });
  }

  /**
   * Stand-in for `cell_clusters/meta_cluster.parquet`.
   *
   * Picks up `uns["<column>_colors"]` when present -- the scanpy convention for a
   * categorical's palette -- and otherwise generates one.
   */
  async metaClusterTable() {
    return this._once('metaCluster', async () => {
      const { clusters } = await this._clusterValues();
      let palette = null;

      if (this.clusterColumn) {
        const [colors, categorical] = await Promise.all([
          this.store.unsArray(`${this.clusterColumn}_colors`),
          this.store.obsCategorical(this.clusterColumn),
        ]);
        if (colors && categorical) {
          palette = categoricalPalette(categorical.categories, colors);
        }
      }

      return buildMetaClusterTable({ clusters, palette });
    });
  }

  /**
   * Duck-types `CBGRowGroupReader.readGene`, so `viz_state.row_group_readers.cbg` can be
   * this adapter and no expression call site changes.
   *
   * Returns the non-zero entries only, with `cell_id` as the cell's position in `obs` --
   * the same integer index the CBG Parquet uses, and the same schema
   * `getGeneExpressionColumns` looks for.
   */
  async readGene(geneName) {
    const names = await this.store.geneNames();
    const index = names.indexOf(geneName);
    if (index === -1) return null;

    // A gene-major layer turns this into a slice of one or two chunks. Falling back to
    // the CSR matrix means downloading all of it, which does not scale past a few tens
    // of MB -- so the layer is what makes large stores usable.
    let column = await this.store.geneFromCscLayer(index);
    if (!column) {
      column = geneColumnSparse(await this.store.csr(), index);
    }

    return new arrow.Table({
      cell_id: arrow.makeVector(column.cellIds),
      expression: arrow.makeVector(column.values),
    });
  }

  /** Expression of one gene across all cells, in `obs` order. */
  async geneExpression(geneName) {
    const [names, csr] = await Promise.all([
      this.store.geneNames(),
      this.store.csr(),
    ]);
    const index = names.indexOf(geneName);
    if (index === -1) {
      throw new Error(`[SpatialDataAdapter] gene "${geneName}" is not in var`);
    }
    return geneColumn(csr, index);
  }
}
