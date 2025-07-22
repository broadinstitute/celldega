export const refresh_layer = (viz_state, layers_obj, layer_name) => {

  console.log('refresh_layer', layer_name);
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
