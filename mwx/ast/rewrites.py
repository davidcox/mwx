''' A collection of AST-tree rewriters for bridging between new MWX syntax and
    old MWXML syntax.
'''
from mwx.ast.templates import *
from mwx.constants import *
import re

registry = []


class DrawsSyntaxRewriter(TreeWalker):

    triggered_types = container_types

    def trigger(self, node):
        if (isinstance(node, MWASTNode) and
            node.obj_type in self.triggered_types):

            return True

        return False

    def action(self, node, parent=None, parent_ctx=None, index=None):
        # parse and rewrite the 'draws' property
        if 'draws' in node.props:
            draws = node.props.pop('draws')

            r = re.compile(r'\"?(\d+)\s*(cycles|samples)\"?')
            m = r.match(draws)

            if m:
                nsamples = int(m.group(1))
                method = m.group(2).upper()

                node.props['nsamples'] = nsamples
                node.props['sampling_method'] = method
            else:
                raise Exception('Invalid "draws" specification: %s' % draws)

registry.append(DrawsSyntaxRewriter)


class TypeAliasRewriter(TreeWalker):

    def trigger(self, node):
        if (isinstance(node, MWASTNode) and
            node.obj_type in type_aliases.keys()):
            return True

        return False

    def action(self, node, parent=None, parent_ctx=None, index=None):
        node.obj_type = type_aliases[node.obj_type]

registry.append(TypeAliasRewriter)


def do_registered_rewrites(tree):

    if getattr(tree, '__iter__', False):
        tree = RootNode(children=tree)
        has_tmp_root = True
    else:
        has_tmp_root = False

    for rewriter_class in registry:
        rewriter = rewriter_class(tree)
        rewriter.walk()
        tree = rewriter.tree

    if has_tmp_root:
        tree = tree.children

    return tree
