import * as d3 from 'd3';

const hexToRgb = (hex) => {
  if (!hex || typeof hex !== 'string') {
    return [59, 130, 246];
  }
  const normalized = hex.replace('#', '');
  if (normalized.length !== 6) {
    return [59, 130, 246];
  }
  const value = parseInt(normalized, 16);
  // eslint-disable-next-line no-bitwise
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
};

const BUTTON_LABELS = {
  row: 'ROW',
  col: 'COL',
};

const DEFAULT_MAX_BARS = 15;

const create_index_map = (nodes = []) =>
  new Map(nodes.map((node, idx) => [String(node.name), idx]));

class CategoryBreakdown {
  constructor(viz_state) {
    this.viz_state = viz_state;
    this.focus_names = { row: [], col: [] };
    this.selected_attribute = { row: null, col: null };
    this.available_attributes = { row: [], col: [] };
    this.active_axis = 'col';
    this.index_maps = {
      row: create_index_map(viz_state.row_nodes || []),
      col: create_index_map(viz_state.col_nodes || []),
    };
    this.axisButtons = {};

    this.container = document.createElement('div');
    this.container.style.display = 'flex';
    this.container.style.flexDirection = 'column';
    this.container.style.gap = '8px';
    this.container.style.width = '100%';

    const buttonRow = document.createElement('div');
    buttonRow.style.display = 'flex';
    buttonRow.style.gap = '12px';

    ['row', 'col'].forEach((axis) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = BUTTON_LABELS[axis];
      button.style.background = 'transparent';
      button.style.border = 'none';
      button.style.padding = '0';
      button.style.fontSize = '11px';
      button.style.fontWeight = '700';
      button.style.letterSpacing = '0.08em';
      button.style.textTransform = 'uppercase';
      button.style.cursor = 'pointer';
      button.addEventListener('click', () => this._set_active_axis(axis));
      this.axisButtons[axis] = button;
      buttonRow.appendChild(button);
    });

    this.message = document.createElement('div');
    this.message.style.fontSize = '11px';
    this.message.style.color = '#6b7280';
    this.message.style.minHeight = '16px';

    this.barContainer = document.createElement('div');
    this.barContainer.className = 'bar_container';
    this.barContainer.style.width = '107px';
    this.barContainer.style.height = '100px';
    this.barContainer.style.marginLeft = '5px';
    this.barContainer.style.border = '1px solid #d3d3d3';
    this.barContainer.style.borderRadius = '6px';
    this.barContainer.style.overflowY = 'auto';
    this.barContainer.style.background = '#ffffff';
    this.barContainer.style.display = 'none';

    this.barContainer.addEventListener('wheel', (event) => {
      const { scrollTop, scrollHeight, clientHeight } = this.barContainer;
      const atTop = scrollTop === 0;
      const atBottom = scrollTop + clientHeight === scrollHeight;

      if ((atTop && event.deltaY < 0) || (atBottom && event.deltaY > 0)) {
        event.preventDefault();
      }
    });

    const svgNode = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svgNode.setAttribute('width', '100');
    this.barSvg = d3.select(svgNode);
    this.barSvg
      .attr('font-family', 'sans-serif')
      .attr('font-size', 11)
      .style('user-select', 'none');
    this.barContainer.appendChild(svgNode);

    this.container.appendChild(buttonRow);
    this.container.appendChild(this.message);
    this.container.appendChild(this.barContainer);

    this._update_axis_buttons();

    this.unsubscribe =
      this.viz_state.obs_store?.focused_dendro?.subscribe?.((focus) =>
        this._on_focus_change(focus)
      ) || null;

    this.update_available_attributes();
    this._render_active();
  }

  _update_axis_buttons() {
    const activeColor = this.viz_state.buttons?.blue || '#2f74ff';
    Object.entries(this.axisButtons).forEach(([axis, button]) => {
      const isActive = axis === this.active_axis;
      button.style.color = isActive ? activeColor : '#6b7280';
      button.style.opacity = isActive ? '1' : '0.7';
      button.style.textDecoration = isActive ? 'underline' : 'none';
    });
  }

  _set_active_axis(axis) {
    if (this.active_axis === axis) {
      return;
    }
    this.active_axis = axis;
    this._update_axis_buttons();
    this._render_active();
  }

  _on_focus_change(focus) {
    if (!focus) {
      this.focus_names.row = [];
      this.focus_names.col = [];
    } else {
      const polygons = this.viz_state.dendro?.polygons?.[focus.axis] || [];
      const polygon = polygons.find(
        (poly) => poly.properties?.name === focus.name
      );
      const names = polygon?.properties?.all_names || [];
      this.focus_names[focus.axis] = names.map((name) => String(name));
      if (focus.axis === 'row') {
        this.focus_names.col = [];
      } else {
        this.focus_names.row = [];
      }
      this._set_active_axis(focus.axis);
    }

    this._render_active();
  }

  _pick_attribute(axis) {
    const names = this.available_attributes[axis] || [];
    if (!names.length) {
      return null;
    }
    const preferred = this.viz_state.manual_cat?.config?.[axis]?.attribute;
    if (preferred && names.includes(preferred)) {
      return preferred;
    }
    if (names.includes('manual_cat')) {
      return 'manual_cat';
    }
    return names[0] || null;
  }

  update_available_attributes() {
    ['row', 'col'].forEach((axis) => {
      const categorical_defs = (this.viz_state.attr.all_defs?.[axis] || []).filter(
        (def) => def.type === 'categorical'
      );
      this.available_attributes[axis] = categorical_defs.map((def) => def.name);
      const current = this.selected_attribute[axis];
      if (current && this.available_attributes[axis].includes(current)) {
        return;
      }
      const preferred = this._pick_attribute(axis);
      this.selected_attribute[axis] = preferred;
    });

    this._render_active();
  }

  _get_definition(axis) {
    const attribute_name = this.selected_attribute[axis];
    if (!attribute_name) {
      return null;
    }
    const definitions = this.viz_state.attr.all_defs?.[axis] || [];
    return (
      definitions.find(
        (def) => def.name === attribute_name && def.type === 'categorical'
      ) || null
    );
  }

  _render_active() {
    this._render_axis(this.active_axis);
  }

  _render_axis(axis) {
    const attr_def = this._get_definition(axis);
    if (!attr_def || !Array.isArray(attr_def.values)) {
      this.barContainer.style.display = 'none';
      this.message.style.display = 'block';
      this.message.textContent = `No categorical attributes for ${
        axis === 'row' ? 'rows' : 'columns'
      }`;
      return;
    }

    const names = this.focus_names[axis] || [];
    const index_map = this.index_maps[axis];
    let target_indices = [];

    if (!names.length) {
      target_indices = attr_def.values.map((_, idx) => idx);
      this.message.style.display = 'block';
      this.message.textContent = `All ${axis === 'row' ? 'rows' : 'columns'}`;
    } else {
      target_indices = names
        .map((name) => index_map.get(String(name)))
        .filter((idx) => idx !== undefined);
      this.message.style.display = 'block';
      if (target_indices.length) {
        this.message.textContent = `${target_indices.length} ${
          axis === 'row' ? 'rows' : 'columns'
        } selected`;
      } else {
        this.message.textContent = 'Selection not found in this attribute';
      }
    }

    if (!target_indices.length) {
      this.barContainer.style.display = 'none';
      return;
    }

    const counts = new Map();
    target_indices.forEach((idx) => {
      const value = attr_def.values[idx];
      if (value === null || value === undefined || value === '') {
        return;
      }
      const key = String(value);
      counts.set(key, (counts.get(key) || 0) + 1);
    });

    const sorted_entries = Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, DEFAULT_MAX_BARS);

    if (!sorted_entries.length) {
      this.barContainer.style.display = 'none';
      this.message.style.display = 'block';
      this.message.textContent = 'No categories found for this selection';
      return;
    }

    const width = 100;
    const bar_height = 15;
    const chart_height = bar_height * (sorted_entries.length + 1);

    const svg = this.barSvg;
    svg.selectAll('*').remove();
    svg.attr('width', width);
    svg.attr('height', chart_height);
    this.barContainer.style.display = 'block';

    const max_value = d3.max(sorted_entries, (entry) => entry[1]) || 1;
    const y_scale = d3
      .scaleBand()
      .domain(d3.range(sorted_entries.length))
      .range([0, bar_height * sorted_entries.length]);
    const x_scale = d3
      .scaleLinear()
      .domain([0, max_value])
      .range([0, width - 10]);

    const color_map = attr_def.color_map || {};
    const bars = svg
      .selectAll('g')
      .data(sorted_entries)
      .join('g')
      .attr('transform', (_, idx) => `translate(2, ${y_scale(idx) + 2})`);

    bars
      .append('rect')
      .attr('fill', (entry) => {
        const rgb = hexToRgb(color_map[entry[0]]);
        return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
      })
      .attr('width', (entry) => x_scale(entry[1]))
      .attr('height', y_scale.bandwidth() - 1);

    bars
      .append('text')
      .attr('fill', '#111827')
      .attr('x', 4)
      .attr('y', y_scale.bandwidth() / 2)
      .attr('dy', '0.35em')
      .attr('font-size', 10)
      .attr('text-anchor', 'start')
      .text((entry) => entry[0]);

    bars
      .append('text')
      .attr('fill', '#4b5563')
      .attr('x', (entry) => Math.min(width - 15, x_scale(entry[1]) + 2))
      .attr('y', y_scale.bandwidth() / 2)
      .attr('dy', '0.35em')
      .attr('font-size', 10)
      .attr('text-anchor', 'start')
      .text((entry) => entry[1]);
  }

  get_element() {
    return this.container;
  }

  finalize() {
    if (typeof this.unsubscribe === 'function') {
      this.unsubscribe();
    }
  }
}

export const create_category_breakdown = (viz_state) =>
  new CategoryBreakdown(viz_state);
