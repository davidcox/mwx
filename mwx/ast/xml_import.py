
from mwx.ast import *
from mwx.constants import shorthand_actions, reverse_type_aliases

registry = []


def registered(c):
    registry.append(c)
    return c


@registered
class PromoteGenericActions (TreeWalker):

    promoted_types = shorthand_actions.keys() + ['assignment']

    def trigger(self, node):

        return (isinstance(node, MWASTNode) and
                node.obj_type == 'action' and
                'type' in node.props and
                node.props['type'].lower() in self.promoted_types)

    def action(self, node, parent=None, parent_ctx=None, index=None):
        action_type = node.props.pop('type').lower()

        # generate a new, specialized version
        if action_type == 'assignment':
            var = node.props.pop('variable', None)
            val = node.props.pop('value', None)

            if var is None or val is None:
                raise Exception('Cannot promote invalid assignment action')
            replacement = AssignmentAction(variable=var, value=val, children=node.children)
        else:
            primary_arg_name = shorthand_actions[action_type]
            primary_arg = node.props.pop(primary_arg_name, None)

            replacement = Action(action_type, primary_arg, props=node.props, children=node.children)

        parent.rewrite(parent_ctx, index, replacement)


@registered
class DeleteMarkers (TreeWalker):

    def trigger(self, node):
        return (isinstance(node, MWASTNode) and
                (node.obj_type == 'action_marker' or
                 node.obj_type == 'transition_marker'))

    def action(self, node, parent=None, parent_ctx=None, index=None):
        parent.remove_node(parent_ctx, index)


@registered
class DeleteJunkProperties (TreeWalker):

    junk_properties = ['description', 'full_name', 'logging']
    junk_defaults = {'interruptible': 'yes'}

    def trigger(self, node):
        return isinstance(node, MWASTNode)

    def action(self, node, parent=None, parent_ctx=None, index=None):
        props = node.props
        for j in self.junk_properties:
            props.pop(j, None)

        for (j, d) in self.junk_defaults.items():
            if props.get(j, False) and props.get(j).lower() == d:
                props.pop(j)


@registered
class ReverseTypeAliasRewriter(TreeWalker):

    def trigger(self, node):
        return (isinstance(node, MWASTNode) and
                node.obj_type in reverse_type_aliases.keys())

    def action(self, node, parent=None, parent_ctx=None, index=None):
        node.obj_type = reverse_type_aliases[node.obj_type]


@registered
class PromoteStateObjects (TreeWalker):

    def trigger(self, node):
        return  (isinstance(node, MWASTNode) and
                 (node.obj_type == 'state' or
                  node.obj_type == 'task_system_state'))

    def action(self, node, parent=None, parent_ctx=None, index=None):

        children = node.children
        actions = []
        transitions = []

        for c in children:
            if c.obj_type == 'action':
                actions.append(c)
            elif c.obj_type == 'transition':
                transitions.append(c)

        replacement = State(actions=actions, transitions=transitions, props=node.props)
        print 'rewriting %d action, %d transitions' % (len(actions), len(transitions))
        parent.rewrite(parent_ctx, index, replacement)


def do_registered_xml_import_rewrites(tree):

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