from xml.sax.saxutils import escape
from copy import deepcopy, copy
import re

PRIMARY_ARG_STRING = "arg"
from mwx.constants import shorthand_actions

isiterable = lambda x: getattr(x, "__iter__", False)

tab = "    "
use_declaration_style_syntax = True
use_declaration_style_syntax_for_states = True


def flatten(x):
    """Flatten a nested list into a single list, e.g. [[1,2],[3]] becomes
       [1,2,3].  Helper function for working with pyparsing.
    """
    result = []

    if x is None:
        return []

    if not isiterable(x):
        return [x]

    for x_ in x:
        if isiterable(x_):
            result += flatten(x_)
        else:
            result.append(x_)

    return result


def quote_once(x):
    """Put double quotes around a string unless there already quotes.
       For xml quoting, where all values must be quoted.
    """
    assert(isinstance(x, str))

    if len(x) == 0:
        return '""'

    if x[0] is '"' and x[-1] is '"':
        return x
    else:
        return '"' + x + '"'


def mwx_properties_block(props):

    if len(props.keys()) == 0:
        return ''

    props = copy(props)
    tag = props.pop('tag', None)

    output_string = '['

    props_strings = []
    if tag is not None:
        props_strings += ['"%s"' % tag]
    props_strings += ['%s=%s' % (kv[0], to_mwx(kv[1])) for kv in props.items()]
    output_string += ", ".join(props_strings)

    output_string += ']'

    return output_string


def mwx_declaration(obj_type, props, declaration_style_syntax=use_declaration_style_syntax):

    output_string = obj_type

    if declaration_style_syntax:
        props = copy(props)
        tag = props.pop('tag')

        if re.search(r'\s|[$@]', tag):
            props['tag'] = tag  # put it back
        else:
            output_string += ' ' + tag

    output_string += mwx_properties_block(props)

    return output_string


def mwx_child_block(children, tablevel=0):

    if len(children) == 0:
        return ''

    output_string = '{\n'

    tabs = tab * tablevel

    output_string += ''.join([to_mwx(child, tablevel + 1) for child in children])

    output_string += tabs + '}'

    return output_string


def to_mwx(obj, tablevel=0, quote_strings=True, mw_type=None):
    """Convert an object to a string in MWX format.  If the object supplies a
       to_mwx method, this is called.  Strings are simply quoted, and lists of
       objects are returned as a comma-delimited list of mwx strings
    """
    if obj is None:
        return 'None'

    if mw_type is not None:
        return mw_type.convert_to_mwx(obj)

    if type(obj) is str:
        if quote_strings:
            return quote_once(obj)
        else:
            return obj

    if getattr(obj, 'to_mwx', False):
        return obj.to_mwx(tablevel=tablevel)

    if isiterable(obj):
        return ", ".join([to_mwx(x) for x in obj])

    return str(obj)


def to_infix(obj, quote_strings=False):
    """Convert an object to a string in MWX format.  If the object supplies a
       to_mwx method, this is called.  Strings are simply quoted, and lists of
       objects are returned as a comma-delimited list of mwx strings
    """
    if obj is None:
        return '""'

    if type(obj) is str:
        if quote_strings:
            return quote_once(obj)
        else:
            return obj

    if getattr(obj, 'to_infix', False):
        return obj.to_infix(quote_strings)

    if isiterable(obj):
        return ", ".join([to_infix(x) for x in obj])

    return str(obj)


class MWASTNode(object):
    """An abstract syntax tree node for MWorks.
    """

    # tokens for signaling whether an object is a child or a property
    # these are used to enable greater code reuse when recursively walking
    # an AST
    PROPERTY_CTX = 0
    CHILD_CTX = 1

    def __init__(self, obj_type, tag=None, props={}, children=[]):

        self.obj_type = obj_type
        self.props = copy(props)

        if self.props == None or self.props == '':
            self.props = {}

        if tag is not None:
            self.props['tag'] = to_mwx(tag, quote_strings=False)

        if isinstance(children, MWASTNode):
            children = [children]

        self.children = flatten(children)

        if self.children == None:
            self.children = []

        self.silent_syntax = False

    @property
    def unresolved(self):
        return False

    @property
    def tag(self):
        if 'tag' in self.props:
            return self.props['tag']
        else:
            return "<undefined>"

    def rewrite(self, ctx, index, new_node):
        """Replace a child or property node (according to the value of ctx) at
           a given index with a new node
        """

        if ctx is self.PROPERTY_CTX:
            self.props[index] = new_node
        elif ctx is self.CHILD_CTX:
            if isiterable(new_node):
                self.children[index] = new_node[0]
                if len(new_node) > 1:
                    for c in range(1, len(new_node)):
                        self.children.insert(index + c, new_node[c])
            else:
                self.children[index] = new_node

    def remove_node(self, ctx, index):
        """Remove a sub-node (child or property)"""
        if ctx is self.PROPERTY_CTX:
            self.props.pop(index)
        elif ctx is self.CHILD_CTX:
            self.children.pop(index)

    def to_xml(self):
        xml = "<%s " % self.obj_type

        for (key, val) in self.props.items():
            val_xml = quote_once(escape(str(val)))
            xml += ' %s=%s' % (key, val_xml)

        xml += ">\n"

        if self.children is not None:
            # try:
            for child in self.children:
                if isinstance(child, MWASTNode):
                    xml += child.to_xml() + "\n"
                elif getattr(child, '__str__', False):
                    xml += str(child) + "\n"
                else:
                    raise Exception("Can't stringify object: %s" + child)
            # except Exception as e:
            #     logging.debug(self.children)
            #     logging.error(e)

        xml += "</%s>" % self.obj_type
        return xml

    def to_ast_string(self, tablevel=0):

        tabs = tab * tablevel

        result = tabs + "- %s [%s]\n" % (self.obj_type, self.tag)
        result += tabs + "\tattributes=%s\n" % self.props

        if len(self.children) > 0:
            result += tabs + "\tchildren:\n"
            for c in self.children:
                if getattr(c, "to_ast_string", False):
                    result += c.to_ast_string(tablevel + 2)
                else:
                    result += tabs + "\tRAW_OBJECT<<<    " + str(c).replace("\n", "\\n") + "   >>>\n"

        return result

    def to_mwx(self, tablevel=0):

        tabs = tab * tablevel

        output_string = tabs

        if self.silent_syntax:
            output_string += '\n# ' + self.tag + '\n\n'
            output_string += ''.join([to_mwx(c) for c in self.children])
            return output_string

        output_string += mwx_declaration(self.obj_type, self.props)

        output_string += mwx_child_block(self.children, tablevel)

        output_string += '\n'

        return output_string


class MWKeyword (object):

    def __init__(self, name):
        self.name = name

    def to_mwx(self, tablevel=0):
        return self.name


class RootNode (MWASTNode):
    """A node representing the root of the document"""

    def __init__(self, children=[]):
        MWASTNode.__init__(self, 'root', children=children)

    def to_xml(self):
        xml = "<mwxml>"

        if self.children is not None:
            # try:
            for child in self.children:
                if isinstance(child, MWASTNode):
                    xml += child.to_xml() + "\n"
                elif getattr(child, '__str__', False):
                    xml += str(child) + "\n"
                else:
                    raise Exception("Can't stringify object: %s" % child)
            # except Exception as e:
            #     logging.debug(self.children)
            #     logging.error(e)

        xml += "</mwxml>"
        return xml

    def to_ast_string(self):
        result = ""

        if len(self.children) > 0:
            for c in self.children:
                if getattr(c, "to_ast_string", False):
                    result += c.to_ast_string()
                else:
                    result += "\tRAW_OBJECT<<<    " + str(c).replace("\n", "\\n") + "   >>>\n"

        return result

    def to_mwx(self):
        return ''.join([to_mwx(c) for c in self.children])


class MWVariable(MWASTNode):

    def __init__(self, tag, default=None, scope='global', var_type=None, props={}, children=[]):

        try:
            props = copy(props)
        except:
            print props
            raise('shit!!')
        if isinstance(props, str):
            props = {}

        if props is None:
            props = {}

        if default is not None:
            props['default_value'] = default

        if scope is None:
            scope = 'global'

        if var_type is None or var_type == 'var':
            var_type = 'float'

        props['scope'] = scope

        props['type'] = var_type

        MWASTNode.__init__(self, 'variable', tag, props=props, children=children)

    def to_mwx(self, tablevel=0):

        props = copy(self.props)

        tag = props.pop('tag')
        scope = props.pop('scope', 'global').lower()
        var_type = props.pop('type', 'var').lower()

        default = props.pop('default_value', '0.0')

        s = tab * tablevel

        if scope == 'local':
            s += 'local '

        s += var_type + ' '
        s += tag
        s += mwx_properties_block(props)
        s += ' = %s' % default

        s += '\n'

        return s


class Action (MWASTNode):
    """A custom node for representing actions.  Provides infrastructure for
       handling a default arg, and automatically generating a convenience
       tag from its type and arguments
    """

    def __init__(self, action_type=None, arg=None, props={}, children=[], alt_tag=None):

        MWASTNode.__init__(self, "action", props=props, children=children)

        if action_type is not None:
            self.props['type'] = action_type

        if arg is not None:
            if not action_type in shorthand_actions:
                self.props[PRIMARY_ARG_STRING] = arg  # TODO: lookup what the real primary arg is
            else:
                self.props[shorthand_actions[action_type]] = arg

        tag = None
        if 'tag' not in self.props:
            if alt_tag is not None:
                tag = alt_tag
            # elif arg is not None and arg.__class__ == str:
            #     self.props['tag'] = action_type + " " + escape(arg.strip('" '))
            elif getattr(arg, "__str__", False):
                tag = action_type + " " + escape(to_mwx(arg, quote_strings=False))
            else:
                tag = action_type

        self.props['tag'] = tag

    def to_mwx(self, tablevel=0):

        tabs = tab * tablevel

        output_string = tabs

        props = copy(self.props)

        if 'type' not in props.keys():
            return MWASTNode.to_mwx(self, tablevel)

        output_string += self.props['type']

        args = []

        if PRIMARY_ARG_STRING in props.keys():
            args.append(to_mwx(self.props[PRIMARY_ARG_STRING]))

        primary_arg_property = shorthand_actions.get(props['type'], None)

        if primary_arg_property is not None:
            args.append(to_mwx(props.pop(primary_arg_property), mw_type=primary_arg_property))

        for key in props.keys():
            if key == PRIMARY_ARG_STRING or key == "tag" or key == "type":
                continue
            args.append("%s=%s" % (key, to_mwx(self.props[key])))

        output_string += "(" + ", ".join(args) + ")"

        output_string += mwx_child_block(self.children, tablevel)
        output_string += '\n'

        return output_string


class ForeignCodeAction (Action):

    def __init__(self, language=None, code=None, **kwargs):

        Action.__init__(self, "foreign_code", **kwargs)

        if language is not None:
            self.props['language'] = language

        if code is not None:
            from xml.sax.saxutils import escape
            self.children = [escape(code)]

    def to_mwx(self, tablevel=0):
        tabs = tab * tablevel
        output_string = "" + tabs

        output_string += self.props['language']

        output_string += "{\n"
        code = self.children[0]
        code_lines = code.split("\n")

        code_tabs = tabs + tab
        code_block = code_tabs + ("\n" + code_tabs).join(code_lines)

        output_string += code_block + "\n"

        output_string += tabs + "}"
        return output_string


class AssignmentAction (Action):

    def __init__(self, variable=None, value=None, **kwargs):

        alt_tag = "%s = %s" % (variable, to_mwx(value))
        kwargs['alt_tag'] = alt_tag

        Action.__init__(self, 'assignment', **kwargs)

        if variable is not None:
            self.props['variable'] = variable

        if value is not None:
            self.props['value'] = value

    def to_mwx(self, tablevel=0):
        tabs = tab * tablevel
        output_string = "" + tabs

        output_string += "%s = %s" % (self.props['variable'], to_mwx(self.props['value'], quote_strings=False))
        output_string += '\n'

        return output_string


class State (MWASTNode):
    """A custom node representing a state system state."""

    def __init__(self, tag=None, actions=[], transitions=[], props={}):

        if tag is None and 'tag' in props:
            tag = props['tag']

        self.actions = actions
        self.transitions = transitions
        children = actions + transitions
        MWASTNode.__init__(self, 'state', tag, children=children, props=props)

    def to_mwx(self, tablevel=0):

        tabs = tab * tablevel
        output_string = tabs

        output_string += mwx_declaration(self.obj_type,
                                         self.props,
                                         use_declaration_style_syntax_for_states)

        # { action\n action\n ... }
        output_string += mwx_child_block(self.actions, tablevel)

        output_string += ' transition '

        # { transition\n transition\n ... }
        output_string += mwx_child_block(self.transitions, tablevel)

        output_string += '\n'
        return output_string


class Transition (MWASTNode):
    """A custom node for representing a transition object.  Provides automatic
       tag from condition and target if one is not provided.
    """

    def __init__(self, condition=None, target=None, **kwargs):
        alt_tag = "%s -> %s" % (to_mwx(condition), to_mwx(target))
        kwargs['alt_tag'] = alt_tag
        kwargs['tag'] = alt_tag
        MWASTNode.__init__(self, 'transition')

        if condition is not None:
            self.props['condition'] = condition
        if target is not None:
            self.props['target'] = target

    def to_mwx(self, tablevel=0):
        tabs = tab * tablevel
        output_string = '' + tabs

        condition = self.props['condition']
        target = self.props['target']

        output_string += "%s -> %s" % (to_mwx(condition, quote_strings=False),
                                       to_mwx(target))

        output_string += '\n'
        return output_string


class DuplicateTemplateNameException(Exception):

    def __init__(self, obj):
        self.obj = obj

    def __str__(self):
        return "Attempt to redefine template %s" % (self.obj.name)


class MWVariableReference (MWASTNode):
    """A class that represents variable references, including those with
       indices supplied in a bracket operator (e.g. x[0])
    """
    def __init__(self, identifier=None, index=None, **kwargs):

        MWASTNode.__init__(self, 'variable_reference', tag=identifier)

        # "index" is the index in the case of an array reference
        if index is '':
            index = None

        self.index = index

        # put the index elements into the parent class children
        # so that recursive evaluation / discovery finds them
        if self.index is not None:
            if isiterable(index):
                self.children += index
            else:
                self.children += [index]

    def to_ast_string(self):
        if self.index is None:
            return "@var(" + self.tag + ")"
        else:
            return "@var(" + self.tag + "[" + str(self.index) + "])"

    def __str__(self):
        if self.index is not None:
            return '%s[%s]' % (self.tag, self.index)
        else:
            if self.tag is None:
                raise Exception('Invalid (empty/None) tag')
            return self.tag

    def __repr__(self):
        return self.__str__()

    def to_mwx(self, tablevel=0):
        return self.__str__()


class MWFunctionCall (MWASTNode):
    """A node representing a function call, with optional arguments"""

    def __init__(self, identifier, fargs=[], **kwargs):

        MWASTNode.__init__(self, 'function_call')

        if identifier is not None:
            self.props['tag'] = identifier

        if fargs is '':
            fargs = None

        if fargs is not None:
            if isiterable(fargs):
                self.children += fargs
            else:
                self.children += [fargs]

    def to_mwx(self, tablevel=0):
        return self.to_infix()

    def to_infix(self, quote_strings=False):
        out = self.props['tag']
        out += '(' + to_mwx(self.children) + ')'
        return out

    def __str__(self):
        return self.to_mwx()


class MWExpression (MWASTNode):
    """A node representing an arithmetic expression"""
    def __init__(self, operator=None, operands=None, **kwargs):

        MWASTNode.__init__(self, "expression")

        self.op = operator
        #self.props['operator'] = operator

        if operands is not None:
            self.children += operands

    @property
    def operands(self):
        return self.props['operands']

    def simplify(self):
        "Check to see if the operands are variables; if not simplify the expression"
        return self

    def __str__(self):
        return self.to_infix()

    def __ast_str__(self):
        if len(self.children) == 1:
            return "[%s: %s]" % (self.op, self.children[0])
        else:
            return "[%s: %s, %s]" % (self.op, self.children[0], self.children[1])

    def __repr__(self):
        return self.__str__()

    def to_ast_string(self, tablevel=0):
        return tab * tablevel + "EXPRESSION[" + self.__ast_str__() + "]"

    def to_mwx(self, tablevel=0):
        return self.to_infix()

    def to_xml(self):
        return self.to_infix()

    def to_infix(self, quote_strings=False):

        if len(self.children) == 1:
            operand = to_infix(self.children[0])
            return "%s %s" % (self.op, operand)
        else:
            op1 = to_infix(self.children[0])
            op2 = to_infix(self.children[1])
            return "(%s %s %s)" % (op1, self.op, op2)

    # this is a bit of a hack for now
    # evaluate an expression at parse time (e.g. for macro control flow)
    def eval(self):
        eval_string = self.to_infix(quote_strings=False)
        try:
            return eval(eval_string)
        except:
            raise Exception("Unable to evaluate expression: %s" % eval_string)


class MWBinaryExpression(MWExpression):
    """A node representing a sub-expression with two operands"""

    def __init__(self, op, operand1, operand2):
        MWExpression.__init__(self, op, (operand1, operand2))

    def simplify(self):

        new_value = self
        operands = self.children
        if getattr(operands[0], "simplify", False):
            operands[0] = operands[0].simplify()

        if getattr(operands[1], "simplify", False):
            operands[1] = operands[1].simplify()

        if (not isinstance(operands[0], MWVariableReference) and
           not isinstance(operands[0], MWExpression) and
           not isinstance(operands[1], MWVariableReference) and
           not isinstance(operands[1], MWExpression)):

            # TODO: this is terribly hacky for moment; care should be taken here
            try:
                o1 = eval(operands[0])
            except:
                o1 = operands[0]

            try:
                o2 = eval(operands[1])
            except:
                o2 = operands[1]

            op = self.op
            new_value = self

            try:
                if op is "+":
                    if isinstance(o1, str) or isinstance(o2, str):  # a type cooercion not allowed in Python
                        o1 = str(o1)
                        o2 = str(o2)
                    new_value = o1 + o2
                elif op is "-":
                    new_value = o1 - o2
                elif op is "*":
                    new_value = o1 * o2
                elif op is "/":
                    new_value = o1 / o2
                elif op is "^":
                    new_value = o1 ^ o2
            except Exception:
                pass

        return new_value


class MWUnaryExpression(MWExpression):
    """A node representing a sub-expression with one operand"""
    def __init__(self, op, operand):
        MWExpression.__init__(self, op, [operand])

    def simplify(self):
        operand = self.children[0]
        op = self.op
        if getattr(operand, "simplify", False):
            operand = operand.simplify()

        new_value = self

        if not isinstance(operand, MWVariableReference) and \
           not isinstance(operand, MWExpression):

            try:
                operand = eval(operand)
            except:
                pass

            try:
                if op is "+":
                    new_value = +operand
                elif op is "-":
                    new_value = -operand
            except:
                pass

        return new_value


def remove_python_padding(code, padding):
    """A helper for normalizing python code in foreign_code actions"""
    padding_len = len(padding)
    lines = code.split("\n")
    for l in range(1, len(lines)):
        try:
            lines[l] = lines[l][padding_len:]
        except:
            pass
    return "\n".join(lines)


class TreeWalker:
    """A base class for walking an AST and performing actions on certain nodes.
       To be useful, `trigger` and `action` should be overridden.  `trigger`
       decides whether a node should be process, and `action` performs some
       action on the triggered node.

       If the `continue_after_trigger` constructor kwarg is set to False, the
       tree walking will not continue recursing after an action is performed.
       This is useful if the action rewrites the tree in a way that makes
       further traversal ill-defined.
    """

    def __init__(self, tree, continue_after_rewrite=True):
        self.tree = tree
        self.continue_after_rewrite = continue_after_rewrite
        self.result = None
        self.rewritten = False

    def reset(self):
        self.rewritten = False

    def trigger(self, node):
        return False

    def action(self, node):
        return None

    def should_descend(self, node):
        return True

    def walk(self):
        self.reset()

        if isiterable(self.tree):
            for t in self.tree:
                self._walk_recursive(t)
        else:
            self._walk_recursive(self.tree)
        return self.result

    def _walk_recursive(self, node, parent=None, parent_context=None, index=None):

        returned_node = None

        # test the trigger on this node
        if(self.trigger(node)):
            returned_node = self.action(node, parent, parent_context, index)

        # if we've been instructed to bail after a single trigger, bail
        if (not self.continue_after_rewrite and returned_node is not None):
            return

        if returned_node is not None:
            node = returned_node

        # decide whether to recurse downward
        if not self.should_descend(node):
            return

        # walk attributes
        if getattr(node, 'props', False):
            for k in node.props.keys():
                p = node.props[k]
                self._walk_recursive(p, node, MWASTNode.PROPERTY_CTX, k)

        # walk children
        if getattr(node, 'children', False):
            for child in node.children:
                c = node.children.index(child)
                self._walk_recursive(child, node, MWASTNode.CHILD_CTX, c)

