const normalizeAxis = (axis) => (axis === 'col' ? 'col' : 'row');

const defaultGetter = () => [];

export class ManualCategoryStore {
  constructor(axis = 'row', getNodeNames = defaultGetter) {
    this.axis = normalizeAxis(axis);
    this.getNodeNames =
      typeof getNodeNames === 'function' ? getNodeNames : defaultGetter;

    this.attribute = null;
    this.values = new Map(); // node_name -> category_value
    this.colors = new Map(); // category_value -> hex
    this.listeners = new Set();
  }

  setAttribute(name) {
    const normalized = name ? String(name) : null;
    if (this.attribute === normalized) return;

    this.attribute = normalized;
    this.values.clear();
    this.colors.clear();
    this.emit();
  }

  updateSelection({ selection = [], value, color }) {
    const normalizedValue =
      value === null || value === undefined || value === ''
        ? null
        : String(value);

    selection.forEach((name) => {
      const key = String(name);
      if (normalizedValue) {
        this.values.set(key, normalizedValue);
      } else {
        this.values.delete(key);
      }
    });

    if (normalizedValue && color) {
      this.colors.set(normalizedValue, String(color));
    }

    this.emit();
  }

  getValueFor(name) {
    if (name === null || name === undefined) return null;

    const key = String(name);
    const stored = this.values.get(key);
    return stored === undefined ? null : stored;
  }

  clear() {
    if (!this.attribute && this.values.size === 0 && this.colors.size === 0) {
      return;
    }
    this.attribute = null;
    this.values.clear();
    this.colors.clear();
    this.emit();
  }

  toFrame(fillValue = 'N.A.') {
    const index = this.getNodeNames().map((name) => String(name));
    const index_name = this.axis === 'row' ? 'row_id' : 'col_id';

    if (!this.attribute) {
      return {
        columns: [],
        index,
        index_name,
        data: {},
      };
    }

    const column = index.map((name) => {
      const stored = this.values.get(String(name));
      return stored === null || stored === undefined || stored === ''
        ? fillValue
        : stored;
    });

    return {
      columns: [this.attribute],
      index,
      index_name,
      data: { [this.attribute]: column },
    };
  }

  toColorPayload(fillValue = 'N.A.', fillColor = '#d1d5db') {
    if (!this.attribute) return {};

    const payload = {
      [this.attribute]: { [fillValue]: fillColor },
    };

    this.colors.forEach((hex, value) => {
      if (!value) return;
      payload[this.attribute][value] = hex;
    });

    return payload;
  }

  toExportPayload() {
    if (!this.attribute) return {};

    const values = {};
    const colors = {};

    this.values.forEach((value, key) => {
      values[String(key)] = value;
    });

    this.colors.forEach((hex, value) => {
      colors[String(value)] = hex;
    });

    return {
      [this.attribute]: {
        values,
        colors,
      },
    };
  }

  subscribe(fn, options = { immediate: true }) {
    this.listeners.add(fn);
    if (!options || options.immediate) {
      fn();
    }
    return () => this.listeners.delete(fn);
  }

  emit() {
    this.listeners.forEach((fn) => fn());
  }
}
