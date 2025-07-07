import * as d3 from 'd3';

import { update_cat, update_selected_cats } from '../global_variables/cat';
import { update_cell_exp_array } from '../global_variables/cell_exp_array';
import { update_selected_genes } from '../global_variables/selected_genes';

export const make_bar_container = () => {
  return document.createElement('div');
};

export const bar_callback_cluster = (
  _event,
  d,
  _deck_ist,
  _layers_obj,
  _viz_state
) => {

  // add cell_layer, path_layer, and trx_layer to the deck_check observable
  console.log('deck_check: bar_callback_cluster');
  _viz_state.obs_store.deck_check.set({
    ..._viz_state.obs_store.deck_check.get(),
    cell_layer: false,
    path_layer: false,
    trx_layer: false,
  });
    
  update_cat(_viz_state.cats, 'cluster');
  update_selected_cats(_viz_state.cats, [d.name], _viz_state.obs_store);
  update_selected_genes(_viz_state.genes, [], _viz_state.obs_store);

};

export const bar_callback_gene = async (
  _event,
  d,
  _deck_ist,
  _layers_obj,
  _viz_state
) => {
  const inst_gene = d.name;
  const reset_gene = inst_gene === _viz_state.cats.cat;
  const new_cat = reset_gene ? 'cluster' : inst_gene;

  update_cat(_viz_state.cats, new_cat);

  console.log('deck_check: bar_callback_gene');
  _viz_state.obs_store.deck_check.set({
    ..._viz_state.obs_store.deck_check.get(),
    cell_layer: false,
    trx_layer: false,
  });
  update_selected_genes(_viz_state.genes, [inst_gene], _viz_state.obs_store);
  // testing setting selected_cats to array with the selected gene for
  // observable updates
  update_selected_cats(_viz_state.cats, [inst_gene], _viz_state.obs_store);
  await update_cell_exp_array(
    _viz_state.cats,
    _viz_state.genes,
    _viz_state.global_base_url,
    inst_gene,
    _viz_state.seg.version,
    _viz_state.vector_name_integer,
    _viz_state.aws
  );

};

export const bar_callback_rgn = (
  _event,
  _d,
  _deck_ist,
  _layers_obj,
  _viz_state
) => {
  // console.log('bar_callback_rgn')
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
