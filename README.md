# celldega

## Installation

```sh
pip install celldega
```

### Note on VIPS Installation
If running on a new Terra.bio workspace you will need to install vips in a startup script (e.g., startup_script.sh) with the following

```
#!/bin/bash
apt update
apt install -y libvips
apt install -y libvips-tools
apt install -y libvips-dev
```

Please see Terra.bio [documentation](https://support.terra.bio/hc/en-us/articles/360058193872-Preconfigure-a-Cloud-Environment-with-a-startup-script) for more information.

## Development installation

Create a virtual environment and and install celldega in *editable* mode with the
optional development dependencies:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

You then need to install the JavaScript dependencies and run the development server.

```sh
npm install
npm run dev
```

Open `example.ipynb` in JupyterLab, VS Code, or your favorite editor
to start developing. Changes made in `js/` will be reflected
in the notebook.

### PyPI
Increment version in `project.toml` and

```
$ hatch build
$ hatch publish
```

#### Hatch Development
```
$ hatch env prune      # Remove old environments
$ hatch env create     # Create a new environment based on pyproject.toml
$ hatch shell          # Activate the new environment
```

### NPM
Increment version in `package.json` and

```
$ npm build
$ npm publish
```

#### Development Notes
May use older version of deck.gl 8.9.1 until bug with instanced layer is resolved using newer versions "^9.0.5".;