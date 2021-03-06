"""This module provides machinery for evaluating mwx templates."""

from ast import *
from copy import copy
import logging
import string


# helper subclass of string.Template for finding '@macro' style substitution
class MWStringTemplate(string.Template):
    delimiter = '@'


def mw_template_string(s, subs):
    return MWStringTemplate(s).substitute(subs)


class SimpleReplacementTreeWalker(TreeWalker):
    """ Walk the AST and replace all a recognized templated references according
        to the supplied replacement_table dictionary
    """
    def __init__(self, tree, replacement_table):
        TreeWalker.__init__(self, tree)
        self.replacement_table = replacement_table

    def reset(self):
        self.result = None

    def trigger(self, node):
        if isinstance(node, TemplateReference):
            return True

        if isinstance(node, str):
            return True

        return False

    def action(self, node, parent=None, parent_ctx=None, index=None):

        if isinstance(node, MWExpression):
            return

        if not isinstance(parent, MWASTNode):
            return None

        if isinstance(node, str):
            new_string = mw_template_string(node, self.replacement_table)
            parent.rewrite(parent_ctx, index, new_string)
            return None

        if getattr(node, 'name', False) and node.name in self.replacement_table:
            replacement = self.replacement_table[node.name]
            parent.rewrite(parent_ctx, index, replacement)
            return None

        return None


class ExpressionSimplifier(TreeWalker):
    """TreeWalker that attempts to simplify arithmetic expression"""
    def __init__(self, tree):
        TreeWalker.__init__(self, tree)

    def trigger(self, node):
        return isinstance(node, MWExpression)

    def action(self, node, parent=None, parent_ctx=None, index=None):
        new_node = node.simplify()
        if new_node != node:
            parent.rewrite(parent_ctx, index, new_node)


class MaximumTreeRewritesExceededException (Exception):
    def __init__(self, n):
        self.n = n

    def __str__(self):
        return "Maximum template descent depth exceeded. " +\
               "Is there an infinite loop in a template?"


def create_template_definition(name=None, args=[], **kwargs):
    t = TemplateDefinition(name, args, **kwargs)
    return t


class TemplateDefinition (MWASTNode):

    def __init__(self, name=None, args=[], **kwargs):

        MWASTNode.__init__(self, 'template_definition', **kwargs)

        # todo: the mapping of this onto the MWASTNode base class is squirrely

        self.body = self.children

        if name is not None:
            self.name = name
            self.props['tag'] = name
        else:
            self.name = self.props['tag']

        if args is not None:
            self.args = args
            self.props['args'] = args  # TODO
        else:
            self.args = self.props['args']

        # deposit the args in the "children" field
        # recursive descent can find them
        # self.children += self.args

        # register this new template
        #if self.name in self.templates:
        #    raise DuplicateTemplateNameException(self)

    def to_xml(self):
        return ''

    def to_mwx(self, tablevel=0):

        output_string = '' + tab * tablevel
        output_string += "def %s" % self.name

        if len(self.args) > 0:
            output_string += '('
            to_mwx(self.args)
            output_string += ')'

        if isiterable(self.body):
            if len(self.body) > 1:
                output_string += "{\n"
                body_content = [to_mwx(x, tablevel + 1) for x in self.body]
                output_string += "\n".join(body_content) + "\n"
                output_string += "}\n"
            else:
                output_string += " = " + to_mwx(self.body[0])
        else:
            output_string += " = " + to_mwx(self.body)

        return output_string

    def __call__(self, args=[], templates={}):
        "Apply the template"

        body = self.body

        if args is None or len(args) is not len(self.args):
            raise Exception("Incorrect number of arguments to template")

        replacement_table = dict(zip(self.args, args))

        # attach the body to a temporary root node
        body_root = RootNode(children=body)

        # apply simple macro-value replacement
        walker = SimpleReplacementTreeWalker(body_root, replacement_table)
        walker.walk()

        new_tree = walker.tree

        # apply a full round of macro evaluation in this context
        template_rewriter = TemplateTreeRewriter(new_tree, templates=templates)
        template_rewriter.rewrite_tree()
        new_tree = template_rewriter.tree.children

        if len(new_tree) == 1:
            new_tree = new_tree[0]

        return new_tree


class TemplateReference (MWASTNode):
    """A node representing a template reference, that is, a reference that
       should be expanded according to a previously defined template definition
    """
    def __init__(self, name=None, args=None, **kwargs):
        MWASTNode.__init__(self, "template_reference", **kwargs)

        if name is not None:
            self.name = name
            self.props['tag'] = name
        else:
            self.name = self.props['tag']

        if args is not None:
            self.args = args
            self.props['args'] = args
        else:
            self.args = self.props['args']

        # deposit the args in the "children" field
        # recursive descent can find them
        self.children += self.args

        self.resolved = False

    @property
    def unresolved(self):
        return not self.resolved

    def resolve(self, templates):
        name = self.name
        args = self.args

        # lookup
        if name not in templates:
            logging.debug("Unknown template %s" % name)
            return None

        # resolve the template arguments, if needed
        def attempt_resolve(arg):
            if getattr(arg, 'resolve', False):
                return arg.resolve(templates)
            else:
                return arg
        args = [attempt_resolve(a) for a in args]

        template = templates[name]

        if len(template.args) != len(args):
            raise InvalidTemplateArgsException(template, self)

        result = template(args, templates=templates)

        return result

    def to_mwx(self, tablevel=0):
        result = tab * tablevel
        result += "@" + self.name
        if self.args is not None and len(self.args) > 0:
            result += "(" + ", ".join(map(str, self.args)) + ")"

        return result


class TemplateIf(MWASTNode):

    def __init__(self, condition, body=[], else_body=[]):

        MWASTNode.__init__(self, 'template_if')

        self.condition = condition
        self.body = flatten(body)
        self.else_body = flatten(else_body)

        self.children = [self.condition] + self.body + self.else_body

        self.resolved = False

    @property
    def unresolved(self):
        return not self.resolved

    def resolve(self, templates):

        # TODO: error handling
        if getattr(self.condition, 'eval', False):
            try:
                c = self.condition.eval()
            except Exception as e:
                logging.debug(e)
                return None
        else:
            try:
                c = eval(self.condition)
            except:
                c = False

        if c:
            return resolve_templates(self.body, templates)
        else:
            return resolve_templates(self.else_body, templates)


class TemplateDefinitionFinder(TreeWalker):
    """A simple AST Walker that finds template definitions and stores them
    """

    def __init__(self, tree):
        TreeWalker.__init__(self, tree)

    def reset(self):
        self.result = {}

    def trigger(self, node):
        if isinstance(node, TemplateDefinition):
            return True
        return False

    def action(self, node, parent=None, parent_ctx=None, index=None):
        #parent.remove_node(parent_ctx, index)
        self.result[node.name] = node


class InvalidTemplateArgsException(Exception):

    def __init__(self, template, reference):
        self.template = template
        self.reference = reference

    def __str__(self):
        n_template_args = len(self.template.args)
        n_reference_args = len(self.reference.args)

        return "Invalid number of arguments to template %s: needs %d arguments, got %d" % \
                        (self.template.name, n_template_args, n_reference_args)


class UnresolvedTemplateReferencesException (Exception):
    def __init__(self, unresolved):
        self.unresolved = unresolved

    def __str__(self):
        return "Unresolved template references: %s" % (str(self.unresolved))


class TemplateReferenceRewriter(TreeWalker):
    """An AST Walker object that finds unresolved template references and
       attempts to fill them in with appropriate content
    """

    def __init__(self, tree, templates):
        TreeWalker.__init__(self, tree)
        self.templates = templates
        self.reset()

    def reset(self):
        self.unresolved_nodes = []
        self.result = self.unresolved_nodes

    def trigger(self, node):

        if getattr(node, 'unresolved', False):
            return node.unresolved
        else:
            return False

    def should_descend(self, node):
        if isinstance(node, TemplateDefinition):
            return False
        elif isinstance(node, TemplateIf):
            return False
        else:
            return True

    def action(self, node, parent=None, parent_ctx=None, index=None):

        template_result = node.resolve(self.templates)

        if template_result is not None:
            node.resolved = True
            parent.rewrite(parent_ctx, index, template_result)
        else:
            self.unresolved_nodes.append(node)


class TemplateTreeRewriter (object):
    """ An object that finds and coordinates the rewriting of templates
        references in an AST.
    """

    def __init__(self, tree, maximum_rewrites=15, templates={}):
        if getattr(tree, '__iter__', False):
            self.tree = RootNode(children=tree)
            self.has_tmp_root_node = True
        else:
            self.tree = tree
            self.has_tmp_root_node = False

        self.templates = copy(templates)
        self.maximum_rewrites = maximum_rewrites

    def find_templates(self):
        walker = TemplateDefinitionFinder(self.tree)
        self.templates.update(walker.walk())

    def rewrite_tree(self):
        # build a dictionary of template declarations
        self.find_templates()

        # build an tree-walker object that will rewrite the tree
        # replacing references with their values
        rewriter = TemplateReferenceRewriter(self.tree, self.templates)

        unresolved = rewriter.walk()
        self.tree = rewriter.tree

        count = 0
        while(len(unresolved) > 0 and count < self.maximum_rewrites):
            unresolved = rewriter.walk()
            logging.debug("Unresolved elements: %s" % unresolved)
            count += 1

        if count == self.maximum_rewrites:
            raise MaximumTreeRewritesExceededException(count)

        if len(unresolved) > 0:
            # TODO come up with a list of what went wrong
            raise UnresolvedTemplateReferencesException(unresolved)

        # Simplify expressions to the extent possible
        simplifier = ExpressionSimplifier(self.tree)
        simplifier.walk()

        self.tree = simplifier.tree

        if self.has_tmp_root_node:
            self.tree = self.tree.children

        return self.tree


def resolve_templates(tree, templates={}):

    tree_rewriter = TemplateTreeRewriter(tree, templates=templates)
    return tree_rewriter.rewrite_tree()
