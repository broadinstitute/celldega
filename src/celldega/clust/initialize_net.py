def main(self, widget=None):
    if not hasattr(self, "meta_cat"):
        self.meta_cat = False

    self.dat = {
        "nodes": {"row": [], "col": []},
        "mat": [],
        "node_info": {},
    }

    for inst_rc in self.dat["nodes"]:
        self.dat["node_info"][inst_rc] = {
            "ini": [],
            "clust": [],
            "rank": [],
            "info": [],
            "cat": [],
            "value": [],
        }

    # check if net has categories predefined
    if not hasattr(self, "persistent_cat_colors"):
        self.persistent_cat_colors = False
        found_cats = False
    else:
        found_cats = True
        inst_cat_colors = self.viz["cat_colors"]
        inst_global_cat_colors = self.viz["global_cat_colors"]

    # initialize matrix colors
    ###########################
    has_matrix_colors = hasattr(self, "viz") and "matrix_colors" in self.viz

    matrix_colors = (
        self.viz["matrix_colors"] if has_matrix_colors else {"pos": "red", "neg": "blue"}
    )

    # add widget if necessary
    if widget is not None:
        self.widget_class = widget

    self.is_downsampled = False

    self.viz = {
        "row_nodes": [],
        "col_nodes": [],
        "links": [],
        "mat": [],
        "matrix_colors": matrix_colors,
    }

    if not found_cats:
        self.viz["cat_colors"] = {"row": {}, "col": {}}
        self.viz["global_cat_colors"] = {}
    else:
        self.viz["cat_colors"] = inst_cat_colors
        self.viz["global_cat_colors"] = inst_global_cat_colors

    self.sim = {}
    self.umap = {}


def viz(self, reset_cat_colors=False):
    # keep track of old cat_colors
    old_cat_colors = self.viz["cat_colors"]
    old_global_cat_colors = self.viz["global_cat_colors"]

    matrix_colors = self.viz.get("matrix_colors", {"pos": "red", "neg": "blue"})

    self.viz = {
        "row_nodes": [],
        "col_nodes": [],
        "links": [],
        "mat": [],
        "matrix_colors": matrix_colors,
    }

    if reset_cat_colors:
        self.viz["cat_colors"] = {"row": {}, "col": {}}
        self.viz["global_cat_colors"] = {}
    else:
        self.viz["cat_colors"] = old_cat_colors
        self.viz["global_cat_colors"] = old_global_cat_colors
