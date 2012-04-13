from ast import *
from numpy import arange
import uuid


def generate_unique_id():
    return str(uuid.uuid1())


# Classes for actually building objects in MW

class TypeFilteredTreeWalker(TreeWalker):

    def __init__(self, tree, filt=None):
        TreeWalker.__init__(self, tree)

        if filt is None:
            self.filter = None
        elif isiterable(filt):
            self.filter = filt
        else:
            self.filter = [filt]

    # decide if this node requires action
    def trigger(self, node):

        if not isinstance(node, MWASTNode):
            return False

        t = node.obj_type

        # ones to always ignore
        if t == 'template_definition':
            return False

        if self.filter is None:
            return True

        if t in self.filter:
            return True

        return False


class CreateObjectPass(TypeFilteredTreeWalker):
    """
        Walk the abstract syntax tree, and instruct MW to create and register
        objects
    """

    def __init__(self, tree, reg, filt=None, anonymous=False):
        TypeFilteredTreeWalker.__init__(self, tree, filt)
        self.mw = reg
        self.anonymous = anonymous

    def action(self, node, parent=None, parent_ctx=None, index=None):
        # if this is a property of an entity, rather than an entity
        if parent_ctx is MWASTNode.PROPERTY_CTX:
            return

        props = node.props

        if 'tag' in node.props and not self.anonymous:
            # TODO: don't overwrite
            tag = node.props['tag']
        else:
            tag = generate_unique_id()
            node.props['tag'] = tag

        if tag is '':
            raise Exception("Cannot create object with empty tag:\n %s" % node.to_ast_string())

        self.mw.create(node.obj_type, tag, props)


class ExpandReplicatorPass(TypeFilteredTreeWalker):
    """
        Walk the abstract syntax tree, and instruct MW to "instance"
        appropriate paradigm component.  In this context, "instance" means
        instantiate an copy of the object that carries its own independent
        local variable context.  Also, at this stage, replicators are
        expanded
    """

    def __init__(self, tree, reg, filt=None):
        TypeFilteredTreeWalker.__init__(self, tree, ['range_replicator',
                                                     'list_replicator'])
        self.mw = reg

    def action(self, node, parent=None, parent_ctx=None, index=None):

        # expand the replicator
        replicator_var = node.props['variable']
        replicator_value_list = []
        if node.obj_type is 'range_replicator':
            from_val = node.props['from']
            to_val = node.props['to']
            step_val = node.props['step']

            # TODO: check float versus integer
            replicator_value_list = arange(from_val, to_val, step_val)
        elif node.obj_type is 'list_replicator':
            raise Exception("not supported yet")

        parent.rewrite(parent_ctx, index, template_result)

        overall_changed, overall_unresolved = self.result

        overall_unresolved.append(template_result)
        self.result = (True, overall_unresolved)

        return


class ConnectPass(TypeFilteredTreeWalker):
    """
        Walk the abstract syntax tree, and instruct MW to connect child obj
        to their parents
    """

    def __init__(self, tree, reg, filt=None):
        TypeFilteredTreeWalker.__init__(self, tree, filt)
        self.mw = reg

    def action(self, node, parent=None, parent_ctx=None, index=None):
        if parent_ctx is not MWASTNode.CHILD_CTX:
            return
        if not isinstance(parent, MWASTNode):
            return
        if not isinstance(node, MWASTNode):
            return
        if isinstance(node, MWExpression) or isinstance(parent, MWExpression):
            return
        if parent.obj_type in ['root', 'template_definition']:
            return

        if 'tag' not in parent.props:
            logging.error('No tag defined: %s' % parent.props)
            return
        parent_name = parent.props['tag']

        child_name = node.props['tag']
        self.mw.connect(parent_name, child_name)

        # TODO error check


class FinalizePass(TypeFilteredTreeWalker):
    """
        Walk the abstract syntax tree, and instruct MW to "finalize" the
        objects
    """

    def __init__(self, tree, reg, filt=None):
        TypeFilteredTreeWalker.__init__(self, tree, filt)
        self.mw = reg

    def action(self, node, parent=None, parent_ctx=None, index=None):
        if parent_ctx is not MWASTNode.CHILD_CTX:
            return
        if not isinstance(parent, MWASTNode):
            return
        if not isinstance(node, MWASTNode):
            return
        if isinstance(node, MWExpression) or isinstance(parent, MWExpression):
            return
        if parent.obj_type is 'template':
            return

        if 'tag' not in node.props:
            raise Exception("Attempting to finalize an object that doesn't have a 'tag' attribute")
        tag = node.props['tag']
        self.mw.finalize(tag)


def mw_pass(tree, reg, cls, filt=None, **kwargs):
    walker = cls(tree, reg, filt, **kwargs)
    walker.walk()
    return tree


def generate_mw_objects(node_tree, reg):

    # Create and register objects with a mw component registry by successively
    # walking the ast and regsitering components

    mw_pass(node_tree, reg, CreateObjectPass, 'variable')
    mw_pass(node_tree, reg, CreateObjectPass, ['stimulus',
                                               'sound',
                                               'iodevice'])

    paradigm_components = ['protocol',
                           'block',
                           'trial',
                           'list']

    mw_pass(node_tree, reg, CreateObjectPass, paradigm_components + ['experiment'])

    mw_pass(node_tree, reg, CreateObjectPass, ['task_system'])
    mw_pass(node_tree, reg, CreateObjectPass, ['state'])
    mw_pass(node_tree, reg, CreateObjectPass, ['action', 'transition'],
            anonymous=True)

    # Expand replicators
    node_tree = mw_pass(node_tree, reg, ExpandReplicatorPass)

    # Connect nodes together
    mw_pass(node_tree, reg, ConnectPass, paradigm_components)
    mw_pass(node_tree, reg, ConnectPass, ['variable', 'stimulus', 'sound'])
    mw_pass(node_tree, reg, ConnectPass, ['iochannel'])
    mw_pass(node_tree, reg, ConnectPass, ['action', 'transition'])

    # Finalize nodes
    mw_pass(node_tree, reg, FinalizePass)
