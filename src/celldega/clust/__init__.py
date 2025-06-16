"""
Optimized hierarchical clustering and visualization for high-dimensional biological data.

This module provides the main Network class for data clustering and the hc() convenience
function for quick clustering operations. Optimized for minimal time/space complexity.
"""

# The Celldega Matrix Vizualization Method is being built using the approaches
# and code adaptations from the Clustergrammer-GL library, which is available at
# github.com/ismms-himc/clustergrammer2
# and being used under the license
#
# MIT License

# Copyright (c) 2021 Nicolas Fernandez

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Import main classes and functions
from .core.network import Network
from .utils import hc


# Public API - this maintains backward compatibility
__all__ = [
    "Network",
    "hc",
]

# Version information (if needed)
__version__ = "1.0.0"
