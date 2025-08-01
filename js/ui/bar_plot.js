import * as d3 from 'd3';

import { new_toggle_cell_layer_visibility } from '../deck-gl/layers/cell_layer';
import { toggle_trx_layer_visibility } from '../deck-gl/layers/trx_layer';
import { update_cat, update_selected_cats } from '../global_variables/cat';
import { update_cell_exp_array } from '../global_variables/cell_exp_array';
import { update_selected_genes } from '../global_variables/selected_genes';
import { toggle_slider } from '../ui/sliders';
import { refresh_layer } from '../utils/refresh_layer';

export const make_bar_container = () => {
  return document.createElement('div');
};

export const bar_callback_cat = (
  _event,
  d,
  _deck_ist,
  _layers_obj,
  _viz_state
) => {
  // ensure that cell button, slider and bars are active
  _viz_state.buttons.buttons.cell.style('color', 'blue');

  toggle_slider(_viz_state.sliders.cell, true);
  _viz_state.cats.svg_bar_cluster.selectAll('rect').style('opacity', 1.0);
  new_toggle_cell_layer_visibility(_layers_obj, true);

  if (_viz_state.nbhd.is_nbhd) {
    _viz_state.obs_store.viz_nbhd_layer.set(false);
    _viz_state.buttons.buttons.nbhd.style('color', 'gray');
  }

  // add cell_layer, path_layer, and trx_layer to the deck_check observable
  _viz_state.obs_store.deck_check.set({
    ..._viz_state.obs_store.deck_check.get(),
    cell_layer: false,
    path_layer: false,
    trx_layer: false,
  });

  update_cat(_viz_state.cats, 'cluster');
  update_selected_cats(_viz_state.cats, [d.name], _viz_state.obs_store);
  update_selected_genes(_viz_state.genes, [], _viz_state.obs_store);

  // toggle gene bars based on reset_cat
  if (_viz_state.cats.reset_cat) {
    _viz_state.genes.svg_bar_gene.selectAll('rect').style('opacity', 1.0);
  } else {
    _viz_state.genes.svg_bar_gene.selectAll('rect').style('opacity', 0.2);
  }
};

export const bar_callback_gene = async (
  _event,
  d,
  _deck_ist,
  _layers_obj,
  _viz_state
) => {

  console.log('bar_callback_gene', d.name);

  // ensure that trx button, slider, and bars are active
  _viz_state.buttons.buttons.trx.style('color', 'blue');

  toggle_slider(_viz_state.sliders.trx, true);
  _viz_state.genes.svg_bar_gene.selectAll('rect').style('opacity', 1.0);

  toggle_trx_layer_visibility(_layers_obj, true);

  if (_viz_state.nbhd.is_nbhd) {
    _viz_state.obs_store.viz_nbhd_layer.set(false);
    _viz_state.buttons.buttons.nbhd.style('color', 'gray');
  }

  const inst_gene = d.name;
  const reset_gene = inst_gene === _viz_state.cats.cat;
  const new_cat = reset_gene ? 'cluster' : inst_gene;

  if (reset_gene) {
    _viz_state.cats.svg_bar_cluster.selectAll('rect').style('opacity', 1.0);
  } else {
    _viz_state.cats.svg_bar_cluster.selectAll('rect').style('opacity', 0.2);
  }

  console.log('update_cat', new_cat);
  update_cat(_viz_state.cats, new_cat);

  console.log('deck_check set for trx_layer and cell_layer');
  _viz_state.obs_store.deck_check.set({
    ..._viz_state.obs_store.deck_check.get(),
    cell_layer: false,
    trx_layer: false,
  });

  console.log('update_selected_genes', [inst_gene]);
  update_selected_genes(_viz_state.genes, [inst_gene], _viz_state.obs_store);
  console.log('update_selected_cats', [inst_gene]);
  update_selected_cats(_viz_state.cats, [inst_gene], _viz_state.obs_store);

  console.log('****** update_cell_exp_array for gene:', inst_gene);
  await update_cell_exp_array(
    _viz_state.cats,
    _viz_state.genes,
    _viz_state.global_base_url,
    inst_gene,
    _viz_state.seg.version,
    _viz_state.vector_name_integer,
    _viz_state.aws
  );
  console.log('****** done updating cell_exp_array for gene:', inst_gene);
};

export const bar_callback_nbhd = (
  _event,
  _d,
  _deck_ist,
  _layers_obj,
  _viz_state
) => {
  // set nbhd to visible
  _viz_state.obs_store.viz_nbhd_layer.set(true);

  // make sure nbhd button is active
  _viz_state.buttons.buttons.nbhd.style('color', 'blue');

  // update selected_nbhds observable with the clicked nbhd unless
  // the clicked nbhd is already equal to selected_nbhds
  const prev_selected_nbhds = _viz_state.obs_store.selected_nbhds.get();
  if (prev_selected_nbhds[0] === _d.name && prev_selected_nbhds.length === 1) {
    _viz_state.obs_store.selected_nbhds.set([]);
  } else {
    _viz_state.obs_store.selected_nbhds.set([_d.name]);
  }

  // refresh the nbhd layer
  refresh_layer(_viz_state, _layers_obj, 'nbhd_layer');

  // highlight the nbhd in the bar plot
  if (_viz_state.obs_store.selected_nbhds.get().length > 0) {
    _viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', (d) => {
      if (d.name === _d.name) {
        return 1.0;
      } else {
        return 0.2;
      }
    });
  } else {
    _viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', 1.0);
  }
};

export const make_bar_graph = (
  bar_container,
  click_callback,
  svg_bar,
  bar_data,
  color_dict,
  deck_ist,
  layers_obj,
  viz_state
) => {
  bar_container.className = 'bar_container';
  bar_container.style.width = '107px';
  bar_container.style.height = '72px';
  bar_container.style.marginLeft = '5px';
  bar_container.style.overflowY = 'auto';
  bar_container.style.border = '1px solid #d3d3d3';

  bar_container.addEventListener('wheel', (event) => {
    const { scrollTop, scrollHeight, clientHeight } = bar_container;
    const atTop = scrollTop === 0;
    const atBottom = scrollTop + clientHeight === scrollHeight;

    if ((atTop && event.deltaY < 0) || (atBottom && event.deltaY > 0)) {
      event.preventDefault();
    }
  });

  const bar_height = 15;
  const svg_height = bar_height * (bar_data.length + 1);

  svg_bar
    .attr('width', 100)
    .attr('height', svg_height)
    .attr('font-family', 'sans-serif')
    .attr('font-size', '13')
    .attr('text-anchor', 'end')
    .style('user-select', 'none');

  bar_container.appendChild(svg_bar.node());

  const max_bar_width = 90;
  const bar_data_values = bar_data.map((x) => x.value);

  const y_new = d3
    .scaleBand()
    .domain(d3.range(bar_data_values.length))
    .range([0, (bar_height + 1) * bar_data_values.length]);

  const x_new = d3
    .scaleLinear()
    .domain([0, d3.max(bar_data_values)])
    .range([0, max_bar_width]);

  const bar = svg_bar
    .selectAll('g')
    .data(bar_data)
    .join('g')
    .attr('transform', (d, i) => `translate(2,${y_new(i) + 2})`)
    .on('click', (event, d) =>
      click_callback(event, d, deck_ist, layers_obj, viz_state)
    );

  bar
    .append('rect')
    .attr('fill', (d) => {
      const inst_rgb = color_dict[d.name];
      return `rgb(${inst_rgb[0]}, ${inst_rgb[1]}, ${inst_rgb[2]})`;
    })
    .attr('width', (d) => x_new(d.value))
    .attr('height', y_new.bandwidth() - 1);

  bar
    .append('text')
    .attr('fill', 'black')
    .attr('x', '5px')
    .attr('y', y_new.bandwidth() / 2 - 1)
    .attr('dy', '0.35em')
    .attr('text-anchor', 'start')
    .text((d) => d.name);
};
