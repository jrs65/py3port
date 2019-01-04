# Python 3 Porting Tools

Tools for porting code to Python 3 (with compatibility for 2).

Built to port CHIME analysis code over. The code in the repository should work
with any code, but the guidelines below contain some specific references to
CHIME code.


## Porting Existing Code

First, *write a test suite*. Anything is better than nothing here, but ideally
it would be a set of automatic tests that determine whether your code is still
working as it should. Unit tests are probably best here, but at the very least
write a script which will utilise a lot of the package functionality and you can
verify the output.

Next you are going to want to setup your test environments. I strongly recommend
using `virtualenv` to create isolated environments for both Python 2.7 and
Python 3 (use the latest version - 3.7 at the time of writing). 
```bash
$ virtualenv --system-site-packages --python=python2.7 venv2
$ virtualenv --system-site-packages --python=python3.7 venv3
```
Once done install your prerequisites into them. If you're porting a set of
packages make sure you use the ported versions of your own dependencies. You may
want to install your own dependencies in an *editable* mode in case porting your
package actually requires fixes in the dependencies, e.g.
```bash
$ git clone git@github.com:radiocosmology/caput.git
$ cd caput
$ pip install -e .
```

Next checkout the repository you want to port. Create a new branch for the
porting (e.g. `python3-support`). *Do not* attempt to install the package (it
almost certainly won't work on Python 3). When you run your tests, either run
them from the root directory of the package, or more reliably, set the
`PYTHONPATH`.

Now, the slightly obvious step of checking that your tests pass in the 2.7
environment *before* changing any code at all.

Now the action happens. Go into the root directory of your package and run
```bash
$ py3port
```
This will start up the porting process. The core of the process is running the
`futurize` tool from [Python Future](http://python-future.org), but wrapped
around it are various pre- and post-processing steps to try and produce better
code. One key feature is that the code will find all non-trivial division
operations and prompt as to whether they should be the new Python 3 float
division (`/`) or Python 2 style floor division (`//`). Take care to answer
these correctly as finding bugs from the incorrect division is quite subtle.

Other transformations that the code will try and do:
- Insert a single `__future__` and `future` import block.
- Use iterators (e.g. `.items()`) in the right contexts. On it's own `futurize`
  will wrap all `.items()` calls within a `list`.
- Remove any `0XXX` octal literals. These are usually a mistake from someone
  zero padding.
- Change any occasions where `int` as a numpy `dtype` argument to using `np.int`
  instead. This removes a clash where `futurize` has changed the meaning of
  `int` and numpy doesn't understand it.
- Change any usage of `x in y.keys()` to `x in y`. This produces nicer code and
  is more Pythonic.

Now check the package against your tests using Python 2.7 (activate the
virtualenv). This usually works pretty well as all the transformations are quite
safe, and so you may not have to make any fixes here. The one exception here is
the use of `__future__.unicode_literals` (see [Strings](#strings) below). Fix up
any issues.

After you've got the code working again on Python 2.7, it's time to move onto
Python 3. This part is usually the harder set of changes and may require some
intensive debugging to get everything working. There are more specific tips
[below](#general-tips).

Congratulations, you've got your code working! Now there's one last step, you
need to ensure your package is still installable.
- Add `future` as a requirement.
- A `setup.py` specifying package data needs a work around as `setuptools` only
  checks the key is a `str` not a `basestring` (see [String](#strings)). To get
  around this, wrap the key in `future.utils.bytes_to_native_str` and use a
  `b""` bytestring.


## General Tips

If you need to use a work around to support Python 2 and 3, that you can remove
when switching entirely to Python 3, mark it with a `# TODO: Python 3
<description>` block so it's easy to find and remove later.

### Strings

Whether to import `__future__.unicode_literals` for porting is somewhat
controversial. It makes code more future proof, but can introduce a large number
of subtle bugs. I've erred on the side of using it, but we'll see how that goes.

To check if an object is a string for both Python 2 and 3 use `isinstance(a,
basestring)` which works for both strings and unicode. One downside to this is
that it means you will need to add a `from past.builtins import basestring`
import which will need to be removed when moving permanently to Python 3.

### Exceptions

Old style exception raising with tracebacks cannot be ported over in a
compatible way. The best option seems to be using the `future.utils.raise_from`
function.

### Travis

Not really a porting issue, but if using travis for CI, getting it to build on
Python 3.7 requires adding
```yaml
sudo: required
dist: xenial
```
at the top level.

### H5PY

Unfortunately `h5py` has a confusing way of dealing with strings. ASCII encoded
strings in an `HDF5` file are usually returned in Python as *byte* strings. This
is fine on Python 2, but causes problems on Python 3. Originally this was a
[bug](https://github.com/h5py/h5py/issues/379), but has been unfixed so long it
is now the expected behavior. This can cause a myriad of problems, but most
often rears its head when dealing with dealing with attributes.

For CHIME, as this is mostly problematic when reading attributes, I have changed
it such that when `memh5` containers (e.g. in memory `andata` objects) are
generated any byte strings will be converted to unicode (within attributes). For
high level code that utlises these containers, this should mostly solve the
problem. The remaining issues are in code that deals directly with the `h5py`
classes (typically code deserialising HDF5 into `memh5` containers), where you
need to manually convert any attributes before use (use the
`memh5.bytes_to_unicode` function).

Another complication is that `h5py` will flat out refuse to write numpy arrays
of unicode strings (that use Numpys own unicode datatype). How to work around
this is mostly covered in the [h5py
documentation](http://docs.h5py.org/en/latest/strings.html). In most cases
changing to the appropriate h5py data type is the right way to go, unfortunately
there's another complication when trying to support *both* Python 2 and 3 as you
must pass it the appropriate unicode type (`unicode` on 2, `str` on 3). To work
around this you should do
```python
# Insert this import somewhere
from future.utils import text_type

# Construct the new datatype with
dt = h5py.special_dtype(vlen=text_type) 

# Which you can use like...
a = np.array([u'hello'])  # h5py incompatible
b = a.astype(dt)  # h5py compatible
```


