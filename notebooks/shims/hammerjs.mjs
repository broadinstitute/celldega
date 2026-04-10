/**
 * esbuild bundles mjolnir/deck with `import * as hammerjs from 'hammerjs'`, but hammer.js
 * is CJS `module.exports = Hammer` only — the namespace has no PointerEventInput, etc.
 * This shim re-exports statics so hammer.browser.js works in a single-file ESM bundle
 * (e.g. nbconvert HTML, jsDelivr).
 */
import H from '../../node_modules/hammerjs/hammer.js';

export const PointerEventInput = H.PointerEventInput;
export const MouseInput = H.MouseInput;
export const Manager = H.Manager;
export const Pan = H.Pan;
export const Rotate = H.Rotate;
export const Pinch = H.Pinch;
export const Swipe = H.Swipe;
export const Press = H.Press;
export const Tap = H.Tap;

export default H;
