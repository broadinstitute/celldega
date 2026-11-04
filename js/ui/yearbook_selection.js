import * as d3 from 'd3';

const SELECTED_COLOR = '#2563eb';
const unique_ids = (values) =>
  [...new Set(Array.isArray(values) ? values : [])].filter(
    (value) => typeof value === 'string'
  );

/** Review selections are cell IDs, independent of the current page/query. */
export const make_yearbook_selection = (root, viz_state) => {
  const model = viz_state.model;
  let selected = new Set(unique_ids(model?.get?.('selected_cells')));
  let disposed = false;

  const overlay = d3
    .select(root)
    .append('div')
    .attr('class', 'yearbook-selection-overlay')
    .style('position', 'absolute')
    .style('inset', '0')
    .style('pointer-events', 'none')
    .style('z-index', '2');

  const render = () => {
    if (disposed) return;
    const {
      cells,
      num_rows,
      num_cols,
      current_page,
      portrait_pixel_size,
      portrait_gap,
    } = viz_state.yearbook;
    const count = num_rows * num_cols;
    const page = cells
      .slice(current_page * count, (current_page + 1) * count)
      .map((cell_id, index) => ({ cell_id, index }));

    const portraits = overlay
      .selectAll('.yearbook-portrait-selection')
      .data(page, (datum) => datum.index)
      .join((enter) => {
        const portrait = enter
          .append('div')
          .attr('class', 'yearbook-portrait-selection')
          .style('position', 'absolute')
          .style('pointer-events', 'none')
          .style('box-sizing', 'border-box')
          .style('border', '2px solid transparent');
        const button = portrait
          .append('button')
          .attr('class', 'yearbook-select-cell')
          .attr('type', 'button')
          .attr('role', 'checkbox')
          .style('position', 'absolute')
          .style('right', '3px')
          .style('bottom', '3px')
          .style('width', '22px')
          .style('height', '22px')
          .style('padding', '3px')
          .style('margin', '0')
          .style('border', '0')
          .style('border-radius', '3px')
          .style('background', 'transparent')
          .style('cursor', 'pointer')
          .style('pointer-events', 'auto');
        const icon = button
          .append('svg')
          .attr('width', 14)
          .attr('height', 14)
          .attr('viewBox', '0 0 14 14')
          .attr('aria-hidden', 'true')
          .style('display', 'block');
        icon
          .append('rect')
          .attr('x', 1)
          .attr('y', 1)
          .attr('width', 12)
          .attr('height', 12)
          .attr('rx', 2)
          .attr('stroke-width', 1.5);
        icon
          .append('path')
          .attr('d', 'M3.5 7 L6 9.5 L10.5 4.5')
          .attr('fill', 'none')
          .attr('stroke', 'white')
          .attr('stroke-width', 1.6)
          .attr('stroke-linecap', 'round')
          .attr('stroke-linejoin', 'round');
        return portrait;
      });

    portraits
      .attr('data-cell-id', (datum) => datum.cell_id)
      .style(
        'left',
        (datum) =>
          `${(datum.index % num_cols) * (portrait_pixel_size + portrait_gap)}px`
      )
      .style(
        'top',
        (datum) =>
          `${Math.floor(datum.index / num_cols) * (portrait_pixel_size + portrait_gap)}px`
      )
      .style('width', `${portrait_pixel_size}px`)
      .style('height', `${portrait_pixel_size}px`)
      .style('border-color', (datum) =>
        selected.has(datum.cell_id) ? SELECTED_COLOR : 'transparent'
      );

    const buttons = portraits
      .select('button')
      .attr('aria-label', (datum) => `Select cell ${datum.cell_id}`)
      .attr('title', (datum) => `Select cell ${datum.cell_id} for review`)
      .attr('aria-checked', (datum) => String(selected.has(datum.cell_id)))
      .style('opacity', (datum) => (selected.has(datum.cell_id) ? '1' : '0.3'))
      .on('pointerdown', (event) => event.stopPropagation())
      .on('mousedown', (event) => event.stopPropagation())
      .on('dblclick', (event) => event.stopPropagation())
      .on('click', (event, datum) => {
        event.stopPropagation();
        toggle(datum.cell_id);
      })
      .on('keydown', (event, datum) => {
        if (event.key === ' ' || event.key === 'Enter') {
          event.preventDefault();
          event.stopPropagation();
          if (!event.repeat) toggle(datum.cell_id);
        }
      })
      .on('mouseenter focus', function () {
        d3.select(this).style('opacity', '1');
      })
      .on('mouseleave blur', function (_event, datum) {
        d3.select(this).style(
          'opacity',
          selected.has(datum.cell_id) ? '1' : '0.3'
        );
      });
    buttons
      .select('rect')
      .attr('fill', (datum) =>
        selected.has(datum.cell_id) ? SELECTED_COLOR : 'transparent'
      )
      .attr('stroke', (datum) =>
        selected.has(datum.cell_id) ? SELECTED_COLOR : '#6b7280'
      );
    buttons
      .select('path')
      .attr('visibility', (datum) =>
        selected.has(datum.cell_id) ? 'visible' : 'hidden'
      );
  };

  const get_selected_cells = () => [...selected];
  const set_selected_cells = (ids) => {
    if (disposed) return;
    selected = new Set(unique_ids(ids));
    render();
    model?.set?.('selected_cells', get_selected_cells());
    model?.save_changes?.();
  };
  const toggle = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    set_selected_cells([...next]);
  };
  const on_selection_change = () => {
    selected = new Set(unique_ids(model.get('selected_cells')));
    render();
  };
  model?.on?.('change:selected_cells', on_selection_change);

  return {
    render,
    get_selected_cells,
    set_selected_cells,
    dispose: () => {
      if (disposed) return;
      disposed = true;
      model?.off?.('change:selected_cells', on_selection_change);
      overlay.remove();
    },
  };
};
