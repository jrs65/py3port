# === Start Python 2/3 compatibility
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future.builtins import *  # noqa  pylint: disable=W0401, W0614
from future.builtins.disabled import *  # noqa  pylint: disable=W0401, W0614
# === End Python 2/3 compatibility

import subprocess
import os
import parso
import click

from . import parso_util

# Disable warning.
click.disable_unicode_literals_warning = True

def context_tree(node, filename, num=3, style=None):
    """Print some context around node.

    Parameters
    ----------
    node : parso node
        Node to give context around.
    filename : string
        Name of file to diplay.
    num : int
        Number of lines of context.
    style : dict
        Styling of nodes. Should be a mapping from parso node to a dictionary
        of parameters given to `click.style`.
    """


    # Add a default style into the dict
    style_dict = {None: {'fg': 'white'}}
    if style:
        style_dict.update(style)

    # Find the start node
    lineno = node.start_pos[0]
    start_line = max(0, lineno - num)
    print_node = node.get_previous_leaf()
    while print_node.line > start_line:
        print_node = print_node.get_previous_leaf()

    # Printer header
    click.secho("==== %s : %i ====" % (filename, lineno))

    # Print (styled) nodes until we reach either the end of file, or have printed enough lines
    while print_node.type != 'endmarker' and print_node.line < lineno + num:
        node_style = style_dict[parso_util.find_ancestor(print_node, style_dict.keys())]
        click.echo(click.style(print_node.get_code(), **node_style), nl=False)
        print_node = print_node.get_next_leaf()



def process_div(tree, filename):
    """Find division operators, prompt for transform, and modify tree.

    Detect any trivial float divisions (and preserve them). Any others are
    prompted to see which type they should be.
    """
    for node in parso_util.pwalk(tree):
        if node.type == 'operator' and node.value == '/':

            # Print out the context around the operator
            click.clear()
            context_tree(
                node, filename, num=8,
                style={
                    node: {'fg':'red'},
                    node.parent: {'fg': 'bright_white', 'bold': True}
                }
            )
            click.echo()


            left_term = node.get_previous_sibling()
            right_term = node.get_next_sibling()
            if (parso_util.is_float_walk(left_term) or
                    parso_util.is_float_walk(right_term)):
                click.echo("Found trivial float division\n")
                continue

            click.echo("Options:")
            click.echo("[F]: Floating point division")
            click.echo("[I]: Integer division using the floor division operator")
            div_type = click.prompt("Division type?", type=click.Choice(["F", "I"]))

            if div_type == 'I':
                node.value = '//'


def process_iterview(tree, filename):
    """Find items/keys/values that can be used in an iterator context.

    This replaces them with the viewitems versions which are correctly
    processed by futurize. Only does anything within the target of a for loop
    and in list/dict comprehensions.
    """
    transform_dict = {
        'items': 'viewitems',
        'iteritems': 'viewitems',
        'keys': 'viewkeys',
        'iterkeys': 'viewkeys',
        'values': 'viewvalues',
        'itervalues': 'viewvalues'
    }

    # Find item and iteritems calls in for loops, and list,dict comprehensions
    for node in parso_util.pwalk(tree):
        if node.type in ['for_stmt', 'comp_for']:
            iterable = parso_util.augment(node.children[3])

            if not (isinstance(iterable, parso_util.FuncCall) and
                    isinstance(iterable.func, parso_util.Attribute)):
                continue

            last_call = iterable.func.attr

            if not last_call.value in transform_dict:
                continue

            last_call.value = transform_dict[last_call.value]

            context_tree(
                node, filename, num=4,
                style={
                    last_call: {'fg':'red'},
                    iterable.node: {'fg': 'bright_white', 'bold': True}
                }
            )


def process_inkeys(tree, filename):
    """Fix the in .keys() anti-pattern

    Not strictly a Python 2->3 issue, but it does make the code uglier once
    converted.
    """
    for node in parso_util.pwalk(tree):
        if node.type != 'comparison':
            continue

        comp_op = node.children[1]

        if not ((comp_op.type == 'keyword' and comp_op.value == 'in') or
                (comp_op.type == 'comp_op' and
                 comp_op.children[1].type == 'keyword' and
                 comp_op.children[1].value == 'in')):
            continue

        target = parso_util.augment(node.children[2])

        if not (isinstance(target, parso_util.FuncCall) and
                isinstance(target.func, parso_util.Attribute)):
            continue

        last_call = target.func.attr

        if last_call.value != 'keys':
            continue

        new_target = parso_util.trim_power(parso_util.trim_power(target.node, node), node)
        if isinstance(new_target, parso_util.TempNode):
            new_target = new_target.full()

        node.children[2] = new_target
        new_target.parent = node

    click.secho("Fixing 'a in x.keys()' antipattern.", bold=True)
    click.echo("\n\n")


def process_octal(tree, filename):
    """Remove unnecessary octal literals.

    There's a bunch of octal numbers that creep in from people trying to
    zero pad integers (WRONG!) in datetimes. This gets rid of them.
    """
    for node in parso_util.pwalk(tree):
        if node.type != 'number':
            continue

        # Check if is an octal number
        if not (len(node.value) > 1 and '.' not in node.value and
                node.value[0] == '0'):
            continue

        context_tree(
            node, filename, num=2,
            style={
                node: {'fg':'red'},
                node.parent: {'fg': 'bright_white', 'bold': True}
            }
        )

        if node.parent.type == 'arglist':
            func = node.parent.parent.get_previous_sibling()
            func = func.children[1] if func.type == 'trailer' else func

            if func.value in ['datetime', 'date']:
                click.echo("Correcting octal number within datetime\n")
                node.value = node.value[1:]


def process_imports(tree, filename):
    """Add Python 2/3 imports.

    Here we remove any existing `__future__` or `builtins` imports and
    replace them with a full set of imports. We carefully transfer over any
    comments and docstrings at the file head.
    """

    import_txt = """# === Start Python 2/3 compatibility
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future.builtins import *  # noqa  pylint: disable=W0401, W0614
from future.builtins.disabled import *  # noqa  pylint: disable=W0401, W0614
# === End Python 2/3 compatibility

"""


    if tree.type != 'file_input':
        raise ValueError("This only works at the module level")

    def is_future_builtin(node):
        return ((node.type == 'import_from' and len(node.get_from_names()) == 1 and
                 node.get_from_names()[0].value in ['__future__', 'builtins']) or
                (node.type == 'simple_stmt' and is_future_builtin(node.children[0])))

    # Remove all redundant __future__ and builtins imports
    orig_first = tree.children[0]  # Needed to sort out header comments below
    tree.children = [n for n in tree.children if not is_future_builtin(n)]

    def has_docstring(node):
        return (node.children[0] != 'simple_stmt' and
                node.children[0].children[0].type == 'string')

    pos = 1 if has_docstring(tree) else 0

    import_tree = parso.parse(import_txt)

    for oi, stmt in enumerate(import_tree.children):
        tree.children.insert(pos + oi, stmt)

    # We may have removed the first node which would have contained any
    # comments at the start of the file, to get around this we will transfer
    # over the prefix if we need to.
    if is_future_builtin(orig_first):
        leaf0 = tree.children[0].get_first_leaf()
        leaf0.prefix = orig_first.get_first_leaf().prefix + leaf0.prefix

    click.secho("Adding imports.", bold=True)
    click.echo("\n\n")


def process_int(tree, filename):
    """Replace `int` when used as a datatype.

    Because of the overriden builtin we can't use `int` as a datatype
    argument for numpy (and we should probably never have been doing so).
    This function replaces them with `np.int`.V
    """

    for node in parso_util.pwalk(tree):

        # Find all uses of `int`
        if not (node.type == 'name' and node.value == 'int'):
            continue

        # Replace where used as a dtype=int keyword argument
        if (node.parent.type == 'argument' and
                node.get_previous_sibling().type == 'operator' and
                node.get_previous_sibling().value == '=' and
                node.parent.children[0].type == 'name' and
                node.parent.children[0].value == 'dtype'):
            node.value = 'np.int'

        # Replace where used solely in an astype
        elif (node.parent.type == 'trailer' and
              node.get_previous_sibling().type == 'operator'):

            func = parso_util.augment(node.parent.parent)

            if not (isinstance(func, parso_util.FuncCall) and
                    isinstance(func.func, parso_util.Attribute)):
                continue

            last_call = func.func.attr

            if last_call.value != 'astype':
                continue

            node.value = 'np.int'


def preprocess(filename):
    """Transformations before futurize called."""

    with open(filename, 'r') as fh:
        tree = parso.parse(fh.read(), version='2.7')

    if tree.children[0].type == 'endmarker':
        return

    process_div(tree, filename)
    process_inkeys(tree, filename)
    process_iterview(tree, filename)
    process_octal(tree, filename)

    with open(filename, 'w') as fh:
        fh.write(tree.get_code())


def postprocess(filename):
    """Transformations after futurize called."""

    with open(filename, 'r') as fh:
        tree = parso.parse(fh.read(), version='2.7')

    if tree.children[0].type == 'endmarker':
        return

    process_imports(tree, filename)
    process_int(tree, filename)

    with open(filename, 'w') as fh:
        fh.write(tree.get_code())


def already_processed(filename):
    """Return True if filename has already been processed.

    Checks for the presence of the future import block.
    """
    test_code = "# === Start Python 2/3 compatibility"

    with open(filename, 'r') as fh:
        src = fh.read()

        return test_code in src


def process(filename):
    """Port a file.
    """

    click.secho("########## %s ###########" % filename, bold=True)

    if already_processed(filename):
        click.secho("File already processed. Skipping...")
        return

    click.secho("Preprocessing:")
    preprocess(filename)

    # Call futurize
    click.secho("Calling futurize:")
    call = ("futurize -0 -u -x libfuturize.fixes.fix_division_safe -w %s" %
            filename)
    subprocess.check_call(call.split())

    click.secho("Post processing:")
    postprocess(filename)


@click.command()
@click.argument('files', nargs=-1)
def main(files):
    """Port code to Python 3 using python-future to maintain Python 2 support.

    Processes the given FILES. If FILES not set, then it will process all
    Python files beneath the current location.'
    """
    if not len(files):
        files = []

        for dirpath, _, filenames in os.walk('.'):

            for name in filenames:

                if not os.path.splitext(name)[1] == '.py':
                    continue

                files.append(os.path.join(dirpath, name))

    for filename in files:
        process(filename)


if __name__ == '__main__':
    main()   # pylint: disable=E1120
