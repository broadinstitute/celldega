## Python
The Celldega library can be installed using pip

Celldega can be installed using pip:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
uv pip install --system celldega
```

Celldega can also be installed with the optional pre-processing requirements (e.g., vips for image pre-processing) using:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
uv pip install --system celldega[pre]
```

## JavaScript

Celldega can be used in a JavaScript environment such as ObservableHQ by importing it as a module from content delivery networks like esm.sh:

```
celldega = await import('https://esm.sh/celldega@latest')
```

Or by importing it from a local file

```
import celldega from 'js/celldega.js'
```