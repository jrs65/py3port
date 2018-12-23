# === Start Python 2/3 compatibility
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future.builtins import *  # noqa  pylint: disable=W0401, W0614
from future.builtins.disabled import *  # noqa  pylint: disable=W0401, W0614
# === End Python 2/3 compatibility

import parso
import wrapt


class ParsoProxy(wrapt.ObjectProxy):
    """A thin wrapper around a parso node.
    """

    def __init__(self, wrapped):
        super(ParsoProxy, self).__init__(wrapped)

        if hasattr(wrapped, 'children'):
            self._self_achildren = wrapped.children
        else:
            self._self_achildren = None

    @property
    def achildren(self):
        return self._self_achildren

    @achildren.setter
    def achildren(self, value):
        self._self_achildren = value


def trim_power(node, parent):
    """Remove the last entry from the power. If only one entry remains,
    return only it.
    """

    if not node.type == 'power':
        raise ValueError('Node type is not power')

    if len(node.children) > 2:
        trimmed_node = TempPower('power', node.children[:-1])
        trimmed_node.parent = parent
    else:
        trimmed_node = node.children[0]

    return trimmed_node


class TempPower(object):
    """Duck-typed power node which doesn't reset the parents."""

    def __init__(self, type_, children):
        self.children = children
        self.type = type_
        self.parent = None

    def full(self):
        node = parso.python.tree.PythonNode(self.type, self.children)
        node.parent = self.parent
        return node

class AugmentedNode(object):

    def __init__(self, node):

        self.node = node
        self.parent = node.parent


class FuncCall(AugmentedNode):
    """Easy wrapper around a function call.
    """

    def __init__(self, node):

        super(FuncCall, self).__init__(node)

        self.func = augment(trim_power(node, self))

        trailer_node = node.children[-1]
        if len(trailer_node.children) > 2:
            # Has arguments...
            if trailer_node.children[1].type == 'arglist':
                self.arguments = [augment(arg) for arg in trailer_node.children[1].children
                                  if arg.type != 'operator' or arg.value != ',']
            else:
                self.arguments = [augment(trailer_node.children[1])]
        else:
            self.arguments = []

        self.achildren = [self.func] + self.arguments

    @classmethod
    def matches(cls, node):

        if node.type != 'power':
            return False

        trailer_node = node.children[-1]

        if trailer_node.type != 'trailer':
            return False

        if (trailer_node.children[0].type != 'operator' or
                trailer_node.children[0].value != '('):
            return False

        if (trailer_node.children[-1].type != 'operator' or
                trailer_node.children[-1].value != ')'):
            return False

        return True


class Attribute(AugmentedNode):
    """Easy wrapper around an Attribute."""

    def __init__(self, node):

        super(Attribute, self).__init__(node)

        self.value = augment(trim_power(node, self))
        self.attr = augment(node.children[-1].children[1])

        self.achildren = [self.value, self.attr]


    @classmethod
    def matches(cls, node):

        if node.type != 'power':
            return False

        trailer_node = node.children[-1]

        if trailer_node.type != 'trailer':
            return False

        if (trailer_node.children[0].type != 'operator' or
                trailer_node.children[0].value != '.'):
            return False

        return True


class Subscript(AugmentedNode):
    """Easy wrapper around subscripting."""

    def __init__(self, node):

        super(Subscript, self).__init__(node)

        self.value = augment(trim_power(node, self))

        trailer_node = node.children[-1]
        if trailer_node.children[1].type == 'subscriptlist':
            self.subscripts = [augment(arg) for arg in trailer_node.children[1].children
                               if arg.type != 'operator' or arg.value != ',']
        else:
            self.subscripts = [augment(trailer_node.children[1])]

        self.achildren = [self.value] + self.subscripts


    @classmethod
    def matches(cls, node):

        if node.type != 'power':
            return False

        trailer_node = node.children[-1]

        if trailer_node.type != 'trailer':
            return False

        if (trailer_node.children[0].type != 'operator' or
                trailer_node.children[0].value != '['):
            return False

        if (trailer_node.children[-1].type != 'operator' or
                trailer_node.children[-1].value != ']'):
            return False

        return True


def augment(tree):
    """An iterator that walks over a parso tree.

    Parameters
    ----------
    tree : parso node
        Root of tree (or subtree) to walk.

    Yields
    ------
    node : parso node
        Node from subtree. Order is complicated.
    """

    augtypes = [FuncCall, Attribute, Subscript]

    # Walk tree yielding nodes

    for type_ in augtypes:
        if type_.matches(tree):
            return type_(tree)

    proxynode = ParsoProxy(tree)

    if hasattr(tree, 'children'):
        proxynode.achildren = [augment(child) for child in proxynode.children]

    return proxynode


def awalk(tree):
    """An iterator that walks over a parso tree.

    Parameters
    ----------
    tree : parso node
        Root of tree (or subtree) to walk.

    Yields
    ------
    node : parso node
        Node from subtree. Order is complicated.
    """

    stack = [tree]

    # Walk tree yielding nodes
    while stack:
        node = stack.pop()

        yield node

        if node.achildren:
            for child in node.achildren[::-1]:
                stack.append(child)


def pwalk(tree):
    """An iterator that walks over a parso tree.

    Parameters
    ----------
    tree : parso node
        Root of tree (or subtree) to walk.

    Yields
    ------
    node : parso node
        Node from subtree. Order is complicated.
    """

    stack = [tree]

    # Walk tree yielding nodes
    while stack:
        node = stack.pop()

        yield node

        if hasattr(node, 'children'):
            for child in node.children[::-1]:
                stack.append(child)


def find_ancestor(node, ancestor_list):
    """See if any item in ancestor_list is an ancestor of node.

    Parameters
    ----------
    node : parso node
        Node to start the search from.
    parent_list : list of nodes
        Ancestor to search for.

    Returns
    -------
    ancestor_node : parso node
        The first ancestor found. Return None if not found.
    """
    while node:
        if node in ancestor_list:
            return node
        node = node.parent
    return None


def is_float(node):
    """Return true if node represents a float."""
    return node.type == 'number' and '.' in node.value
