import { is_orbit_technology } from '../../global_variables/image_info';

const CAMERA_PICKING_RESTORE_DELAY_MS = 250;
const HOVER_PICKING_RESTORE_DELAY_MS = 100;
const CAMERA_REASON = 'camera';
const HOVER_REASON = 'hover';

const is_point_cloud_viz = (viz_state) => {
  const technology = viz_state.img?.landscape_parameters?.technology;
  return is_orbit_technology(technology);
};

const ensurePickabilityState = (viz_state) => {
  if (!viz_state.interaction_pickability) {
    viz_state.interaction_pickability = {};
  }

  const state = viz_state.interaction_pickability;
  state.paused = Boolean(state.paused);
  state.previousDeckPickable = state.previousDeckPickable ?? true;
  state.restoreTimers = state.restoreTimers || {};
  state.pauseReasons =
    state.pauseReasons instanceof Set
      ? state.pauseReasons
      : new Set(state.pauseReasons || []);
  state.eventHandlersAttached = Boolean(state.eventHandlersAttached);

  return state;
};

const clearRestoreTimer = (state, reason) => {
  if (state.restoreTimers[reason]) {
    clearTimeout(state.restoreTimers[reason]);
    state.restoreTimers[reason] = null;
  }
};

const clearAllRestoreTimers = (state) => {
  Object.keys(state.restoreTimers).forEach((reason) => {
    clearRestoreTimer(state, reason);
  });
};

const pausePickability = (deck_ist, viz_state, reason) => {
  const state = ensurePickabilityState(viz_state);
  clearRestoreTimer(state, reason);

  if (!state.paused) {
    state.paused = true;
    state.previousDeckPickable = deck_ist.props?._pickable !== false;

    deck_ist.setProps({
      _pickable: false,
    });
  }

  state.pauseReasons.add(reason);
  return state;
};

const restorePickability = (deck_ist, viz_state, reason) => {
  const state = ensurePickabilityState(viz_state);
  clearRestoreTimer(state, reason);
  state.pauseReasons.delete(reason);

  if (!state.paused || state.pauseReasons.size > 0) {
    return false;
  }

  if (viz_state.edit?.mode === 'sktch') {
    state.paused = false;
    state.previousDeckPickable = true;
    return false;
  }

  deck_ist.setProps({
    _pickable: state.previousDeckPickable,
  });

  state.paused = false;
  state.previousDeckPickable = true;
  return true;
};

const getDeckCanvas = (deck_ist) =>
  deck_ist.getCanvas?.() || deck_ist.canvas || null;

const makeDeckPointerMoveEvent = (deck_ist, event) => {
  const canvas = getDeckCanvas(deck_ist);
  const rect = canvas?.getBoundingClientRect?.();
  if (!rect) {
    return null;
  }

  return {
    type: 'pointermove',
    offsetCenter: {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    },
    center: {
      x: event.clientX,
      y: event.clientY,
    },
    leftButton: false,
    rightButton: false,
    srcEvent: event,
  };
};

const runDelayedHoverPick = (deck_ist, viz_state) => {
  const state = ensurePickabilityState(viz_state);
  const hoverEvent = state.delayedHoverEvent;
  state.delayedHoverEvent = null;

  if (
    !hoverEvent ||
    state.paused ||
    state.pauseReasons.size > 0 ||
    deck_ist.props?._pickable === false ||
    viz_state.edit?.mode === 'sktch'
  ) {
    return;
  }

  if (
    typeof deck_ist._onPointerMove === 'function' &&
    typeof deck_ist._pickAndCallback === 'function'
  ) {
    deck_ist._onPointerMove(hoverEvent);
    deck_ist._pickAndCallback();
  }
};

const schedulePickabilityRestore = (deck_ist, viz_state, reason, delay) => {
  const state = ensurePickabilityState(viz_state);
  clearRestoreTimer(state, reason);

  state.restoreTimers[reason] = setTimeout(() => {
    const restored = restorePickability(deck_ist, viz_state, reason);
    if (reason === HOVER_REASON && restored) {
      runDelayedHoverPick(deck_ist, viz_state);
    }
  }, delay);
};

export const restore_point_cloud_pickability_now = (deck_ist, viz_state) => {
  if (!is_point_cloud_viz(viz_state)) {
    return;
  }

  const state = ensurePickabilityState(viz_state);
  clearAllRestoreTimers(state);
  state.pauseReasons.clear();
  state.delayedHoverEvent = null;

  if (state.paused && viz_state.edit?.mode !== 'sktch') {
    deck_ist.setProps({
      _pickable: state.previousDeckPickable,
    });
  }

  state.paused = false;
  state.previousDeckPickable = true;
};

export const pause_point_cloud_pickability = (
  deck_ist,
  _layers_obj,
  viz_state
) => {
  if (!is_point_cloud_viz(viz_state)) {
    return;
  }

  pausePickability(deck_ist, viz_state, CAMERA_REASON);
  schedulePickabilityRestore(
    deck_ist,
    viz_state,
    CAMERA_REASON,
    CAMERA_PICKING_RESTORE_DELAY_MS
  );
};

export const pause_point_cloud_hover_pickability = (
  deck_ist,
  viz_state,
  event
) => {
  if (!is_point_cloud_viz(viz_state)) {
    return;
  }

  const hoverEvent = makeDeckPointerMoveEvent(deck_ist, event);
  if (!hoverEvent) {
    return;
  }

  const state = pausePickability(deck_ist, viz_state, HOVER_REASON);
  state.delayedHoverEvent = hoverEvent;
  schedulePickabilityRestore(
    deck_ist,
    viz_state,
    HOVER_REASON,
    HOVER_PICKING_RESTORE_DELAY_MS
  );
};

export const setup_point_cloud_pickability_events = (deck_ist, viz_state) => {
  if (!is_point_cloud_viz(viz_state)) {
    return;
  }

  const state = ensurePickabilityState(viz_state);
  if (state.eventHandlersAttached) {
    return;
  }

  const canvas = getDeckCanvas(deck_ist);
  const target = canvas?.parentElement || canvas || viz_state.root;
  if (!target?.addEventListener) {
    return;
  }

  const onPointerMove = (event) => {
    if (event.buttons) {
      return;
    }

    pause_point_cloud_hover_pickability(deck_ist, viz_state, event);
  };

  const onPointerDown = () => {
    restore_point_cloud_pickability_now(deck_ist, viz_state);
  };

  const listenerOptions = {
    capture: true,
    passive: true,
  };

  target.addEventListener('pointermove', onPointerMove, listenerOptions);
  target.addEventListener('pointerdown', onPointerDown, listenerOptions);
  target.addEventListener('click', onPointerDown, listenerOptions);

  state.eventHandlersAttached = true;
  state.eventTarget = target;
  state.eventHandlers = {
    onPointerMove,
    onPointerDown,
  };
};
