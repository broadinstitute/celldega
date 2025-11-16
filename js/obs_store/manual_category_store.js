const normalizeAxis = (axis) => (axis === 'col' ? 'col' : 'row');

const defaultGetter = () => [];

export class ManualCategoryStore {
  constructor(axis = 'row', getNodeNames = defaultGetter) {
    this.axis = normalizeAxis(axis);
    this.getNodeNames = typeof getNodeNames === 'function' ? getNodeNames : defaultGetter;
    this.attribute = null;
    this.values = new Map();
    this.colors = new Map();
    this.listeners = new Set();
  }

  setAttribute(name) {
    const normalized = name ? String(name) : null;
    if (this.attribute === normalized) {
      return;
    }
    this.attribute = normalized;
    this.values.clear();
    this.colors.clear();
    this.emit();
  }

  updateSelection({ selection = [], value, color }) {
    const normalizedValue =
      value === null || value === undefined || value === '' ? null : String(value);

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
    if (!this.attribute) {
      return {
        columns: [],
        index,
        index_name: this.axis === 'row' ? 'row_id' : 'col_id',
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
      index_name: this.axis === 'row' ? 'row_id' : 'col_id',
      data: { [this.attribute]: column },
    };
  }

  toColorPayload(fillValue = 'N.A.', fillColor = '#d1d5db') {
    if (!this.attribute) {
      return {};
    }
    const payload = {
      [this.attribute]: { [fillValue]: fillColor },
    };

    this.colors.forEach((hex, value) => {
      if (!value) {
        return;
      }
      payload[this.attribute][value] = hex;
    });

    return payload;
  }

  toExportPayload() {
    if (!this.attribute) {
      return {};
    }
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

  fromExportPayload(payload) {
    this.values.clear();
    this.colors.clear();

    if (!payload || typeof payload !== 'object') {
      this.attribute = null;
      this.emit();
      return;
    }

    const entries = Object.entries(payload);
    if (entries.length === 0) {
      this.attribute = null;
      this.emit();
      return;
    }

    const [attribute, entry] = entries[0];
    this.attribute = attribute ? String(attribute) : null;

    const values = (entry && entry.values) || {};
    Object.entries(values).forEach(([key, value]) => {
      if (value === null || value === undefined || value === '') {
        return;
      }
      this.values.set(String(key), String(value));
    });

    const colors = (entry && entry.colors) || {};
    Object.entries(colors).forEach(([value, hex]) => {
      if (!hex) {
        return;
      }
      this.colors.set(String(value), String(hex));
    });

    this.emit();
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
