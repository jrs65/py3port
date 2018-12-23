# Python 3 Porting Tools

Tools for porting code to Python 3 (with compatibility for 2).

Built to port CHIME analysis code over.

## Porting Notes

Things to be aware of:
- Remember to add `future` as a requirement.
- To check if an object is a string for both use `isinstance(a, basestring)`
  which works for both strings and unicode. One downside to this is that it
  means `from past.builtins import basestring` imports get added which will
  need to be removed when we move permanently to Python 3.
- Old style exception raising with tracebacks cannot be ported over in a
  compatible way. My recommendation is to remove these and put a note to use
  exception chaining when moving fully to Python 3. This is pretty rare so
  there isn't an automatic attempt to fix this.
