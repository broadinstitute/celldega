import * as d3 from 'd3';

const AXIS_LABELS = {
  row: 'Rows',
  col: 'Columns',
};

const DEFAULT_MAX_BARS = 15;

const create_index_map = (nodes) =>
  new Map(nodes.map((node, idx) => [String(node.name), idx]));

class CategoryBreakdown {
  constructor(viz_state) {
    this.viz_state = viz_state;
    this.focus_names = { row: [], col: [] };
    this.selected_attribute = { row: null, col: null };
    this.available_attributes = { row: [], col: [] };
    this.active_axis = 'row';
    this.index_maps = {
      row: create_index_map(viz_state.row_nodes || []),
      col: create_index_map(viz_state.col_nodes || []),
    };
    this.axisButtons = {};

    this.container = document.createElement('div');
    this.container.style.display = 'flex';
    this.container.style.flexDirection = 'column';
    this.container.style.gap = '12px';
    this.container.style.width = '100%';

    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.flexDirection = 'column';
    header.style.gap = '8px';

    const title = document.createElement('span');
    title.textContent = 'Category breakdown';
    title.style.fontSize = '13px';
    title.style.fontWeight = '600';
    title.style.color = '#1f2a37';
    header.appendChild(title);

    const toggleWrapper = document.createElement('div');
    toggleWrapper.style.display = 'flex';
    toggleWrapper.style.gap = '8px';

    ['row', 'col'].forEach((axis) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = AXIS_LABELS[axis];
      button.style.flex = '1';
      button.style.padding = '6px 8px';
      button.style.border = '1px solid #d3d3d3';
      button.style.borderRadius = '4px';
      button.style.cursor = 'pointer';
      button.style.fontSize = '12px';
      button.addEventListener('click', () => this._set_active_axis(axis));
      this.axisButtons[axis] = button;
      toggleWrapper.appendChild(button);
    });

    header.appendChild(toggleWrapper);

    const selectLabel = document.createElement('label');
    selectLabel.textContent = 'Attribute';
    selectLabel.style.fontSize = '12px';
    selectLabel.style.fontWeight = '600';
    selectLabel.style.color = '#4b5563';

    this.attributeSelect = document.createElement('select');
    this.attributeSelect.style.marginTop = '4px';
    this.attributeSelect.style.width = '100%';
    this.attributeSelect.style.padding = '4px';
    this.attributeSelect.style.border = '1px solid #d3d3d3';
    this.attributeSelect.style.borderRadius = '4px';
    this.attributeSelect.style.fontSize = '12px';
    this.attributeSelect.addEventListener('change', () => {
      this.selected_attribute[this.active_axis] =
        this.attributeSelect.value || null;
      this._render_active();
    });

    selectLabel.appendChild(this.attributeSelect);
    header.appendChild(selectLabel);

    this.message = document.createElement('div');
    this.message.style.fontSize = '11px';
    this.message.style.color = '#6b7280';
    this.message.style.minHeight = '18px';

    this.svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    this.svg.setAttribute('width', '100%');
    this.svg.setAttribute('height', '180');
    this.svg.style.display = 'none';

    this.container.appendChild(header);
    this.container.appendChild(this.message);
    this.container.appendChild(this.svg);

    this._update_axis_buttons();

    this.unsubscribe =
      this.viz_state.obs_store?.focused_dendro?.subscribe?.(
        (focus) => this._on_focus_change(focus),
        { immediate: true }
      ) || null;

    this.update_available_attributes();
    this._render_active();
  }

  _update_axis_buttons() {
    Object.entries(this.axisButtons).forEach(([axis, button]) => {
      const isActive = axis === this.active_axis;
      button.style.background = isActive ? '#1f2937' : '#ffffff';
      button.style.color = isActive ? '#ffffff' : '#1f2937';
    });
  }

  _set_active_axis(axis) {
    if (this.active_axis === axis) {
      return;
    }
    this.active_axis = axis;
    this._update_axis_buttons();
    this._populate_attribute_select();
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

  update_available_attributes() {
    ['row', 'col'].forEach((axis) => {
      const categorical_defs = (this.viz_state.attr.all_defs?.[axis] || []).filter(
        (def) => def.type === 'categorical'
      );
      this.available_attributes[axis] = categorical_defs.map((def) => def.name);

      if (
        !this.selected_attribute[axis] ||
        !this.available_attributes[axis].includes(this.selected_attribute[axis])
      ) {
        this.selected_attribute[axis] = this.available_attributes[axis][0] || null;
      }
    });

    this._populate_attribute_select();
    this._render_active();
  }

  _populate_attribute_select() {
    const options = this.available_attributes[this.active_axis] || [];
    this.attributeSelect.innerHTML = '';

    if (!options.length) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'No categorical attributes';
      this.attributeSelect.appendChild(option);
      this.attributeSelect.disabled = true;
      this.message.textContent = `No categorical attributes available for ${
        this.active_axis === 'row' ? 'rows' : 'columns'
      }`;
      this.svg.style.display = 'none';
      return;
    }

    this.attributeSelect.disabled = false;
    options.forEach((name) => {
      const option = document.createElement('option');
      option.value = name;
      option.textContent = name;
      this.attributeSelect.appendChild(option);
    });

    const preferred = this.selected_attribute[this.active_axis];
    if (preferred && options.includes(preferred)) {
      this.attributeSelect.value = preferred;
    } else {
      this.attributeSelect.value = options[0];
      this.selected_attribute[this.active_axis] = options[0];
    }
  }

  _render_active() {
    this._render_axis(this.active_axis);
  }

  _render_axis(axis) {
    const attribute_name = this.selected_attribute[axis];
    if (!attribute_name || this.attributeSelect.disabled) {
      this.svg.style.display = 'none';
      if (this.attributeSelect.disabled) {
        this.message.style.display = 'block';
      }
      return;
    }

    const definitions = this.viz_state.attr.all_defs?.[axis] || [];
    const attr_def = definitions.find((def) => def.name === attribute_name);

    if (!attr_def || !Array.isArray(attr_def.values)) {
      this.svg.style.display = 'none';
      this.message.style.display = 'block';
      this.message.textContent = 'Attribute values unavailable';
      return;
    }

    const names = this.focus_names[axis] || [];
    const index_map = this.index_maps[axis];
    let target_indices = [];

    if (!names.length) {
      target_indices = attr_def.values.map((_, idx) => idx);
      this.message.style.display = 'block';
      this.message.textContent = `Showing counts for all ${
        axis === 'row' ? 'rows' : 'columns'
      }`;
    } else {
      target_indices = names
        .map((name) => index_map.get(String(name)))
        .filter((idx) => idx !== undefined);
      this.message.style.display = target_indices.length ? 'none' : 'block';
      if (!target_indices.length) {
        this.message.textContent = 'Selection not found in this attribute';
      }
    }

    if (!target_indices.length) {
      this.svg.style.display = 'none';
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

    if (sorted_entries.length === 0) {
      this.svg.style.display = 'none';
      this.message.style.display = 'block';
      this.message.textContent = 'No categories found for this selection';
      return;
    }

    const width = 220;
    const bar_height = 18;
    const chart_height = sorted_entries.length * bar_height + 40;

    const svg = d3.select(this.svg);
    svg.selectAll('*').remove();
    svg.attr('width', width);
    svg.attr('height', chart_height);
    svg.style.display = 'block';

    const margin = { top: 20, right: 12, bottom: 10, left: 90 };
    const chart_width = width - margin.left - margin.right;
    const chart = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const x_scale = d3
      .scaleLinear()
      .domain([0, d3.max(sorted_entries, (entry) => entry[1]) || 1])
      .range([0, chart_width]);

    const y_scale = d3
      .scaleBand()
      .domain(sorted_entries.map((entry) => entry[0]))
      .range([0, chart_height - margin.top - margin.bottom])
      .padding(0.15);

    const color_map = attr_def.color_map || {};

    chart
      .selectAll('rect')
      .data(sorted_entries)
      .enter()
      .append('rect')
      .attr('x', 0)
      .attr('y', (entry) => y_scale(entry[0]))
      .attr('width', (entry) => x_scale(entry[1]))
      .attr('height', y_scale.bandwidth())
      .attr('fill', (entry) => color_map[entry[0]] || '#3b82f6')
      .attr('rx', 4);

    chart
      .selectAll('text.category')
      .data(sorted_entries)
      .enter()
      .append('text')
      .attr('class', 'category')
      .attr('x', -10)
      .attr('y', (entry) => (y_scale(entry[0]) || 0) + y_scale.bandwidth() / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'end')
      .attr('fill', '#1f2937')
      .attr('font-size', 11)
      .text((entry) => entry[0]);

    chart
      .selectAll('text.count')
      .data(sorted_entries)
      .enter()
      .append('text')
      .attr('class', 'count')
      .attr('x', (entry) => x_scale(entry[1]) + 6)
      .attr('y', (entry) => (y_scale(entry[0]) || 0) + y_scale.bandwidth() / 2)
      .attr('dy', '0.35em')
      .attr('fill', '#4b5563')
      .attr('font-size', 11)
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
