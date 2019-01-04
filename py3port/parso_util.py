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
        self._self_aparent = None

    @property
    def achildren(self):
        return self._self_achildren

    @achildren.setter
    def achildren(self, value):
        self._self_achildren = value

    @property
    def aparent(self):
        return self._self_aparent

    @achildren.setter
    def aparent(self, value):
        self._self_aparent = value

def trim_power(node, parent):
    """Remove the last entry from the power. If only one entry remains,
    return only it.
    """

    if not node.type == 'power':
        raise ValueError('Node type is not power')

    if len(node.children) > 2:
        trimmed_node = TempNode('power', node.children[:-1])
        trimmed_node.parent = parent
    else:
        trimmed_node = node.children[0]

    return trimmed_node


class TempNode(object):
    """Duck-typed node which doesn't reset the parents."""

    def __init__(self, type_, children):
        self.children = children
        self.type = type_
        self.parent = None

    def full(self):
        node = parso.python.tree.PythonNode(self.type, self.children)
        node.parent = self.parent
        return node

    def get_code(self):

        code = ""
        for child in self.children:
            code += child.get_code()
        return code

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

        for child in self.achildren:
            child.aparent = self


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

        for child in self.achildren:
            child.aparent = self

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

        for child in self.achildren:
            child.aparent = self

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


class BinOp(AugmentedNode):
    """Easy wrapper around an Attribute."""

    def __init__(self, node):

        if node.type == 'atom':
            node = node.children[1]

        super(BinOp, self).__init__(node)

        self.left = augment(node.children[0])
        self.operator = augment(node.children[1])

        temp_right = TempNode(node.type, node.children[2:]) if len(node.children) > 3 else node.children[2]
        self.right = augment(temp_right)

        self.achildren = [self.left, self.operator, self.right]

        for child in self.achildren:
            child.aparent = self

    @classmethod
    def matches(cls, node):

        # Any parentheses should decay
        if node.type == 'atom':
            if len(node.children) != 3:
                return False

            first = node.children[0]
            last = node.children[2]
            if not (first.type == 'operator' and first.value == '(' and
                    last.type == 'operator' and last.value == ')'):
                return False

            return cls.matches(node.children[1])


        if node.type not in ['arith_expr', 'term', 'power']:
            return False

        if len(node.children) < 3:
            return False

        if node.type == 'power' and (node.children[1].type != 'operator' or node.children[1].value != '**'):
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

    augtypes = [FuncCall, Attribute, Subscript, BinOp]

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
    return node.type == 'number' and ('.' in node.value or 'e' in node.value.lower())


def is_float_walk(node):
    """Traverse the subtree to see if there are any float literals that would
    cause the type of node to be floating point."""
    anode = augment(node)


    arith_op = ['+', '-', '*', '/', '%', '**']
    constants = ['np.pi', 'math.pi']
    floatfunc = ['np.sin', 'np.cos', 'np.tan', 'np.sinh', 'np.cosh', 'np.tanh',
                 'np.exp', 'np.log', 'np.log10', 'np.sqrt', 'float']
    stack = [anode]

    # Walk tree yielding nodes
    while stack:
        node = stack.pop()

        if isinstance(node, parso.python.tree.Number) and is_float(node):
            return True

        elif isinstance(node, BinOp) and node.operator.value in arith_op:
            stack.append(node.left)
            stack.append(node.right)

        elif isinstance(node, Attribute):

            code = node.node.get_code()

            if code.strip() in constants:
                return True

        elif isinstance(node, FuncCall):

            if isinstance(node.func, Attribute):
                code = node.func.node.get_code()
            elif isinstance(node.func, parso.python.tree.Name):
                code = node.func.get_code()
            else:
                continue

            if code.strip() in floatfunc:
                return True

    return False
