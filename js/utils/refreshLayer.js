export const refreshLayer = (viz_state, layers_obj, layer_name) => {
  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    [layer_name]: false,
  });

  viz_state.layers_obj = layers_obj;

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    [layer_name]: true,
  });
};
