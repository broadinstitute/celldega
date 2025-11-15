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
    this.sections = {};
    this.index_maps = {
      row: create_index_map(viz_state.row_nodes || []),
      col: create_index_map(viz_state.col_nodes || []),
    };

    this.container = document.createElement('div');
    this.container.style.display = 'flex';
    this.container.style.flexDirection = 'column';
    this.container.style.gap = '16px';
    this.container.style.width = '100%';

    ['row', 'col'].forEach((axis) => {
      this.sections[axis] = this._create_section(axis);
      this.container.appendChild(this.sections[axis].wrapper);
    });

    this.unsubscribe =
      this.viz_state.obs_store?.focused_dendro?.subscribe?.(
        (focus) => this._on_focus_change(focus),
        { immediate: true }
      ) || null;

    this.update_available_attributes();
    this._render_axis('row');
    this._render_axis('col');
  }

  _create_section(axis) {
    const wrapper = document.createElement('div');
    wrapper.style.display = 'flex';
    wrapper.style.flexDirection = 'column';
    wrapper.style.gap = '8px';

    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.flexDirection = 'column';

    const title = document.createElement('span');
    title.textContent = `${AXIS_LABELS[axis]} categories`;
    title.style.fontSize = '13px';
    title.style.fontWeight = '600';
    title.style.color = '#1f2a37';

    const select = document.createElement('select');
    select.style.marginTop = '6px';
    select.style.width = '100%';
    select.style.padding = '4px';
    select.style.border = '1px solid #d3d3d3';
    select.style.borderRadius = '4px';
    select.style.fontSize = '12px';
    select.addEventListener('change', () => this._render_axis(axis));

    header.appendChild(title);
    header.appendChild(select);

    const message = document.createElement('div');
    message.style.fontSize = '11px';
    message.style.color = '#6b7280';
    message.style.minHeight = '20px';

    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', '160');
    svg.style.display = 'none';

    wrapper.appendChild(header);
    wrapper.appendChild(message);
    wrapper.appendChild(svg);

    return { wrapper, select, svg, message };
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
    }

    this._render_axis('row');
    this._render_axis('col');
  }

  update_available_attributes() {
    ['row', 'col'].forEach((axis) => {
      const section = this.sections[axis];
      const previous = section.select.value;
      section.select.innerHTML = '';

      const categorical_defs = (this.viz_state.attr.all_defs?.[axis] || []).filter(
        (def) => def.type === 'categorical'
      );

      if (categorical_defs.length === 0) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No categorical attributes';
        section.select.appendChild(option);
        section.select.disabled = true;
      } else {
        section.select.disabled = false;
        categorical_defs.forEach((def) => {
          const option = document.createElement('option');
          option.value = def.name;
          option.textContent = def.name;
          section.select.appendChild(option);
        });
      }

      if (previous && Array.from(section.select.options).some((opt) => opt.value === previous)) {
        section.select.value = previous;
      }
    });

    this._render_axis('row');
    this._render_axis('col');
  }

  _get_selected_attribute(axis) {
    const value = this.sections[axis].select.value;
    return value || null;
  }

  _get_focus_for_axis(axis) {
    return this.focus_names[axis] || [];
  }

  _render_axis(axis) {
    const section = this.sections[axis];
    const names = this._get_focus_for_axis(axis);
    const attribute_name = this._get_selected_attribute(axis);

    if (!attribute_name || section.select.disabled) {
      section.svg.style.display = 'none';
      section.message.style.display = 'block';
      section.message.textContent = 'No categorical attributes available';
      return;
    }

    if (!names.length) {
      section.svg.style.display = 'none';
      section.message.style.display = 'block';
      section.message.textContent = 'Select a dendrogram group to view counts';
      return;
    }

    const definitions = this.viz_state.attr.all_defs?.[axis] || [];
    const attr_def = definitions.find((def) => def.name === attribute_name);

    if (!attr_def || !Array.isArray(attr_def.values)) {
      section.svg.style.display = 'none';
      section.message.style.display = 'block';
      section.message.textContent = 'Attribute values unavailable';
      return;
    }

    const index_map = this.index_maps[axis];
    const counts = new Map();

    names.forEach((name) => {
      const idx = index_map.get(String(name));
      if (idx === undefined) {
        return;
      }
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
      section.svg.style.display = 'none';
      section.message.style.display = 'block';
      section.message.textContent = 'No categories found in this selection';
      return;
    }

    const width = 220;
    const bar_height = 18;
    const chart_height = sorted_entries.length * bar_height + 40;

    const svg = d3.select(section.svg);
    svg.selectAll('*').remove();
    svg.attr('width', width);
    svg.attr('height', chart_height);
    svg.style.display = 'block';
    section.message.style.display = 'none';

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
