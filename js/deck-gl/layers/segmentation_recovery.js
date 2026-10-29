import { refresh_layer } from '../../utils/refresh_layer';

let recoverySequence = 0;

// deck.gl clears update flags after an updater throws, so a partially updated
// layer needs fresh GPU state to recover. Retry once per committed data set.
export const create_segmentation_error_handler = (viz_state) => {
  let attempted = false;
  let pending = false;

  const onError = (error) => {
    const layer = viz_state.layers_obj?.path_layer;
    if (viz_state.disposed || !layer || layer.props.onError !== onError) {
      return false;
    }
    if (pending) return true;
    if (attempted) return false;

    attempted = true;
    pending = true;
    const { id } = layer;
    const { data } = layer.props;
    const datasetUrl = viz_state.global_base_url;
    const segmentationVersion = viz_state.seg?.version;
    // eslint-disable-next-line no-console -- Capture context for intermittent GPU failures.
    console.error('[segmentation] Rebuilding failed boundary layer:', {
      datasetUrl,
      segmentationVersion,
      pathCount: data?.length,
      layerId: id,
      error,
    });

    // Leave the active render/update cycle before notifying deck observers.
    queueMicrotask(() => {
      pending = false;
      const layers = viz_state.layers_obj;
      const latest = layers?.path_layer;
      if (
        viz_state.disposed ||
        !latest ||
        latest.id !== id ||
        latest.props.data !== data ||
        latest.props.onError !== onError ||
        viz_state.global_base_url !== datasetUrl ||
        viz_state.seg?.version !== segmentationVersion
      ) {
        return;
      }
      layers.path_layer = latest.clone({
        id: `${id}-recovery-${++recoverySequence}`,
      });
      refresh_layer(viz_state, layers, 'path_layer');
    });
    return true;
  };

  return onError;
};
