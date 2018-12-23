# Python 3 Porting Tools

Tools for porting code to Python 3 (with compatibility for 2).

Built to port CHIME analysis code over.

## Porting Notes

Tips:
- Add a test suite. Anything is better than nothing!
- Remember to add `future` as a requirement.
- `setup.py` with a package data needs a work around as `setuptools` only
  checks the key is a `str` not a `basestring`. To get around this, wrap the
 key in `future.utils.bytes_to_native_str` and use a `b""` bytestring.
- To check if an object is a string for both use `isinstance(a, basestring)`
  which works for both strings and unicode. One downside to this is that it
  means `from past.builtins import basestring` imports get added which will
  need to be removed when we move permanently to Python 3.
- Old style exception raising with tracebacks cannot be ported over in a
  compatible way. The best option seems to be using the
  `future.utils.raise_from` function.
- Old versions of Sphinx seem to have issues.
- If using travis for CI, getting it to build on 3.7 requires adding
  ```yaml
  sudo: required
  dist: xenial
  ```
  at the top level.
