/* global require */

// PIC: the control-panel button that saves a screenshot with a description.
describe('add_pic_button', () => {
  let add_pic_button;
  let screenshot_png;

  beforeEach(() => {
    const fs = require('fs');
    const path = require('path');
    const source = fs
      .readFileSync(path.join(__dirname, '../ui/pic_button.js'), 'utf8')
      .replace(/^import .*;$/gm, '')
      .replace(/^export const /gm, 'const ');
    screenshot_png = jest.fn(() => new Blob(['PNG'], { type: 'image/png' }));
    add_pic_button = new Function(
      'screenshot_png',
      `${source}\nreturn add_pic_button;`
    )(screenshot_png);
    document.body.innerHTML = '';
  });

  const panel = () => {
    const ui = document.createElement('div');
    const row = document.createElement('div');
    row.className = 'search_logo_row';
    const input = document.createElement('input');
    const logo = document.createElement('div');
    logo.className = 'logo_button';
    row.append(input, logo);
    ui.appendChild(row);
    document.body.appendChild(ui);
    return { ui, row, logo };
  };

  const SAVED = {
    schema: 'celldega.view',
    version: 2,
    image: { png: 'UE5H' },
    observed_state: { kind: 'landscape' },
  };

  const setup = (shot = { snapshot: SAVED }) => {
    const { ui, row, logo } = panel();
    const model = { send: jest.fn() };
    const capture = jest.fn(() => shot);
    const pic = add_pic_button(ui, { model, capture });
    return { ui, row, logo, model, capture, pic };
  };

  const dialog = () => document.querySelector('.celldega-pic-dialog');
  const action = (label) =>
    [...dialog().querySelectorAll('[role="button"]')].find(
      (b) => b.textContent === label
    );

  test('sits in the search row, just before the logo, as an all-caps text button', () => {
    const { row, logo, pic } = setup();
    expect(pic.button.textContent).toBe('PIC');
    expect(pic.button.nextSibling).toBe(logo);
    expect(pic.button.parentNode).toBe(row);
  });

  test('captures on click, then saves with a title and description', () => {
    const { model, capture, pic } = setup();
    pic.button.click();
    expect(capture).toHaveBeenCalledTimes(1);
    dialog().querySelector('input').value = ' Glomerulus ';
    dialog().querySelector('textarea').value = 'Podocyte-like ring.';
    action('SAVE').click();
    // The image and state travel once, inside the saved view.
    expect(model.send).toHaveBeenCalledWith({
      event: 'pic',
      id: 1,
      title: 'Glomerulus',
      description: 'Podocyte-like ring.',
      snapshot: SAVED,
    });
    expect(dialog().textContent).toContain('Saving…');
  });

  test('waits for an asynchronous capture before allowing a save', async () => {
    let finish;
    const pending = new Promise((resolve) => {
      finish = resolve;
    });
    const { model, pic } = setup(pending);
    pic.button.click();
    action('SAVE').click();
    expect(model.send).not.toHaveBeenCalled();
    finish({ snapshot: SAVED });
    await Promise.resolve();
    action('SAVE').click();
    expect(model.send).toHaveBeenCalledWith(
      expect.objectContaining({ snapshot: SAVED })
    );
  });

  test("shows Python's reply, and ignores other messages", () => {
    jest.useFakeTimers();
    try {
      const { pic } = setup();
      pic.button.click();
      action('SAVE').click();
      expect(pic.on_message({ event: 'state' })).toBe(false);
      expect(
        pic.on_message({ event: 'pic_saved', id: 1, path: 'shots/a.png' })
      ).toBe(true);
      expect(dialog().textContent).toContain('Saved shots/a.png');
      jest.advanceTimersByTime(2000);
      expect(dialog()).toBeNull();

      pic.button.click();
      action('SAVE').click();
      pic.on_message({ event: 'pic_error', id: 2, error: 'disk full' });
      expect(dialog().textContent).toContain('Not saved: disk full');
    } finally {
      jest.useRealTimers();
    }
  });

  test('Escape cancels; nothing to capture means nothing is sent', () => {
    const { model, pic } = setup(null);
    pic.button.click();
    expect(dialog().textContent).toContain('Nothing to capture');
    action('SAVE').click();
    expect(model.send).not.toHaveBeenCalled();
    dialog().dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(dialog()).toBeNull();
  });

  test('standalone PIC downloads a complete saved view without a kernel', async () => {
    jest.useFakeTimers();
    const click = jest
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {});
    URL.createObjectURL = jest.fn(() => 'blob:saved-view');
    URL.revokeObjectURL = jest.fn();
    try {
      const { ui } = panel();
      const saved = {
        schema: 'celldega.view',
        version: 2,
        image: { png: 'PNG' },
        state: { focus_gene: 'MUC2' },
      };
      const pic = add_pic_button(ui, {
        model: {},
        capture: () => ({ snapshot: saved }),
      });
      pic.button.click();
      dialog().querySelector('textarea').value = 'Boundary observation';
      action('SAVE').click();
      const blob = URL.createObjectURL.mock.calls[0][0];
      expect(blob.type).toBe('image/png');
      expect(screenshot_png).toHaveBeenCalledWith(
        {
          ...saved,
          title: '',
          description: 'Boundary observation',
          author: 'you',
        },
        { title: '' }
      );
      expect(click).toHaveBeenCalledTimes(1);
      expect(dialog().textContent).toContain('Downloaded saved view');
      jest.advanceTimersByTime(1000);
      expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:saved-view');
    } finally {
      click.mockRestore();
      delete URL.createObjectURL;
      delete URL.revokeObjectURL;
      jest.useRealTimers();
    }
  });

  test('without a search row it goes next to the logo; dispose removes it', () => {
    const ui = document.createElement('div');
    const logo = document.createElement('div');
    logo.className = 'logo_button';
    ui.appendChild(logo);
    const pic = add_pic_button(ui, {
      model: { send: jest.fn() },
      capture: () => null,
    });
    expect(pic.button.nextSibling).toBe(logo);
    pic.dispose();
    expect(ui.textContent).not.toContain('PIC');
  });
});
