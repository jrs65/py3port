# Python 2/3 compatibility
# pylint: disable=unused-import, redefined-builtin, no-name-in-module
# noqa: F401
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future.builtins import (ascii, bytes, chr, dict, filter, hex, input,
                             int, map, next, oct, open, pow, range, round,
                             str, super, zip)
from future.builtins.disabled import (apply, cmp, coerce, execfile, file, long,
                                      raw_input, reduce, reload, unicode,
                                      xrange, StandardError)
__version__ = "0.1.0"
