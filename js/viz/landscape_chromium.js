import { Deck, ScatterplotLayer, OrthographicView } from 'deck.gl';
import * as d3 from 'd3';
import { arrayBufferToArrowTable } from '../read_parquet/arrayBufferToArrowTable';
import { options, set_options } from '../global_variables/fetch_options';

const load_table = async (model, trait, url) => {
  const bytes = model.get(trait);
  let buffer;
  if (bytes) {
    buffer = bytes.buffer;
  } else {
    const resp = await fetch(url, options.fetch);
    buffer = await resp.arrayBuffer();
  }
  return arrayBufferToArrowTable(buffer);
};

export const landscape_chromium = async (
  model,
  el,
  base_url,
  token,
  width = 600,
  height = 600
) => {
  set_options(token);

  const meta_cell = await load_table(
    model,
    'meta_cell_parquet',
    `${base_url}/cell_metadata.parquet`
  );
  const meta_cluster = await load_table(
    model,
    'meta_cluster_parquet',
    `${base_url}/cell_clusters/meta_cluster.parquet`
  );
  const meta_gene = await load_table(
    model,
    'meta_gene_parquet',
    `${base_url}/meta_gene.parquet`
  );

  const cells = [];
  const names = meta_cell.getChild('name').toArray();
  const geomCol = meta_cell.getChild('geometry');
  const clusterCol = meta_cell.getChild('cluster').toArray();
  for (let i = 0; i < meta_cell.numRows; i++) {
    const coords = geomCol.get(i);
    cells.push({
      name: String(names[i]),
      x: coords[0],
      y: coords[1],
      cluster: String(clusterCol[i]),
    });
  }

  const cluster_names = meta_cluster
    .getChild('__index_level_0__')
    .toArray()
    .map(String);
  const colors = meta_cluster.getChild('color').toArray();
  const counts = meta_cluster.getChild('count').toArray();

  const color_dict = {};
  const cluster_data = [];
  cluster_names.forEach((name, i) => {
    const c = d3.color(String(colors[i])) || d3.color('#808080');
    color_dict[name] = [c.r, c.g, c.b];
    cluster_data.push({ name, value: Number(counts[i]) });
  });
  cluster_data.sort((a, b) => b.value - a.value);

  const gene_names = meta_gene.getChild('__index_level_0__').toArray();
  const gene_means = meta_gene.getChild('mean').toArray();
  const gene_data = gene_names.map((n, i) => ({
    name: String(n),
    value: Number(gene_means[i]),
  }));
  gene_data.sort((a, b) => b.value - a.value);

  const xExtent = d3.extent(cells, (d) => d.x);
  const yExtent = d3.extent(cells, (d) => d.y);
  const centerX = (xExtent[0] + xExtent[1]) / 2;
  const centerY = (yExtent[0] + yExtent[1]) / 2;
  const range = Math.max(xExtent[1] - xExtent[0], yExtent[1] - yExtent[0]);
  const iniZoom = Math.log2(Math.min(width, height) / range);

  let selected_cluster = null;

  const make_layer = () =>
    new ScatterplotLayer({
      id: 'cell-layer',
      data: cells,
      radiusMinPixels: 2,
      pickable: true,
      getPosition: (d) => [d.x, d.y],
      getFillColor: (d) => {
        const base = color_dict[d.cluster] || [100, 100, 100];
        if (!selected_cluster || d.cluster === selected_cluster) {
          return [...base, 255];
        }
        return [...base, 40];
      },
    });

  const layer = make_layer();
  const deck = new Deck({
    parent: el,
    width,
    height,
    views: [new OrthographicView({ id: 'ortho' })],
    controller: true,
    initialViewState: { target: [centerX, centerY, 0], zoom: iniZoom },
    layers: [layer],
    getTooltip: ({ object }) => (object ? object.name : null),
  });

  // -- UI containers --
  const ui = document.createElement('div');
  ui.style.display = 'flex';
  ui.style.flexDirection = 'row';
  ui.style.marginBottom = '4px';

  const clusterDiv = document.createElement('div');
  const geneDiv = document.createElement('div');
  ui.appendChild(clusterDiv);
  ui.appendChild(geneDiv);

  const barHeight = 14;
  const clusterScale = d3
    .scaleLinear()
    .domain([0, d3.max(cluster_data, (d) => d.value)])
    .range([0, 120]);

  const clusterSvg = d3
    .create('svg')
    .attr('width', 140)
    .attr('height', barHeight * cluster_data.length + 10);
  clusterDiv.appendChild(clusterSvg.node());

  const clusterG = clusterSvg
    .selectAll('g')
    .data(cluster_data)
    .enter()
    .append('g')
    .attr('transform', (_d, i) => `translate(0, ${i * barHeight})`)
    .on('click', (_evt, d) => {
      selected_cluster = selected_cluster === d.name ? null : d.name;
      deck.setProps({ layers: [make_layer()] });
    });

  clusterG
    .append('rect')
    .attr('fill', (d) =>
      d3.color(String(colors[cluster_names.indexOf(d.name)])).formatHex()
    )
    .attr('width', (d) => clusterScale(d.value))
    .attr('height', barHeight - 2);
  clusterG
    .append('text')
    .attr('x', (d) => clusterScale(d.value) + 2)
    .attr('y', barHeight / 2)
    .attr('dominant-baseline', 'middle')
    .attr('font-size', '10px')
    .text((d) => d.name);

  const geneScale = d3
    .scaleLinear()
    .domain([0, d3.max(gene_data, (d) => d.value)])
    .range([0, 120]);
  const geneSvg = d3
    .create('svg')
    .attr('width', 140)
    .attr('height', barHeight * gene_data.length + 10);
  geneDiv.appendChild(geneSvg.node());

  const geneG = geneSvg
    .selectAll('g')
    .data(gene_data)
    .enter()
    .append('g')
    .attr('transform', (_d, i) => `translate(0, ${i * barHeight})`);

  geneG
    .append('rect')
    .attr('fill', '#999')
    .attr('width', (d) => geneScale(d.value))
    .attr('height', barHeight - 2);
  geneG
    .append('text')
    .attr('x', (d) => geneScale(d.value) + 2)
    .attr('y', barHeight / 2)
    .attr('dominant-baseline', 'middle')
    .attr('font-size', '10px')
    .text((d) => d.name);

  el.appendChild(ui);
};
