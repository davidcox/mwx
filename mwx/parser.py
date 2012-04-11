
from pyparsing import *
import re
from copy import deepcopy

from mwx.ast import *
from mwx.constants import *
from mwx.ast.xml_export import do_registered_rewrites
from mwx.ast.xml_import import do_registered_xml_import_rewrites


# Helper functions

def nested_array_to_dict(a):
    """Convert a nested array of key-value pairs (from pyparsing) to a
       dictionary
    """
    d = {}

    if a is not None and a != '':
        for pair in a:
            d[pair[0]] = pair[1]
    return d


def list_to_literals(list_of_names):
    """Convert a list of strings to an OR'd sequence of pyparsing Literal
       objects
    """
    p = Literal(list_of_names[0])
    for l in list_of_names[1:]:
        p = p | Literal(l)

    return p


def dummy_token(name):
    """A pyparsing token allows for more sensible error reporting.  It does
       not match any content, but its name will be used if an error occurs
       is an OR'd sequences where the dummy_token is the first element.
    """
    exception_token = NoMatch()
    exception_token.setName(name.upper())
    return exception_token


def print_parser_error(pe, input_string=None):
    """Pretty-print a parser error, including a listing of the code that
       generated the error
    """
    from sys import stderr

    if input_string == None:
        input_string = pe.pstr

    stderr.write("On line %d, col %d\n" % (pe.lineno, pe.col))
    stderr.write(pe.msg)
    stderr.write("\n")

    col = pe.col
    lines = input_string.split("\n")
    preceding = lines[pe.lineno - 2]
    following = lines[pe.lineno]
    stderr.write("%4d:    %s\n" % (pe.lineno - 1, preceding))
    stderr.write("%4d: -->%s\n" % (pe.lineno, pe.line))
    stderr.write(" " * (col + 8) + "^\n")
    stderr.write("%4d:    %s\n" % (pe.lineno + 1, following))


class MWXParser:
    """A parser object for the 'MWX' lightweight MWorks DSL."""

    # for use with significant-whitespace grammars
    indent_stack = [1]

    def __init__(self, **kwargs):

        use_significant_whitespace = kwargs.pop("significant_whitespace", False)

        # ------------------------------
        # Parser Combinator Definitions
        # ------------------------------

        # Parsers in pyparsing take the form of a large collection of
        # parser object instantiations that handle snippets of syntax
        # and assemblies thereof.
        # At the end of the day, we're aiming towards a final parser
        # object that will accept a full document

        # ------------------------------
        # Style and symbols
        # ------------------------------
        # Definition of block syntax.

        block = None
        if use_significant_whitespace:
            block_open = Suppress(":")
            block = lambda x, p: block_open + (indentedBlock(x, self.indent_stack, True))(p)
        else:
            block_open = Suppress("{")
            block_close = Suppress("}")
            block = lambda x, p: block_open + OneOrMore(x)(p) + block_close

        # Some other stylistic variations
        prop_list_open = Suppress("[")
        prop_list_close = Suppress("]")

        arg_list_open = Suppress("(")
        arg_list_close = Suppress(")")

        index_operator_open = Suppress("[")
        index_operator_close = Suppress("]")

        if use_significant_whitespace:
            action_list_marker = Suppress("actions")
            transition_list_marker = Suppress("transitions")
        else:
            action_list_marker = empty
            transition_list_marker = Suppress("transition")

        assign = Literal("=")
        macro_symbol = Suppress("@")
        def_keyword = Suppress("macro")

        # triple_quote = Suppress("\"\"\"")

        # ------------------------------
        # Forward declarations
        # ------------------------------

        # Things that will be recursively embedded later
        object_declaration = Forward()
        expression = Forward()
        value = Forward()

        def quoted_string_fn(drop_quotes=True):
            dq = QuotedString('"', "\\", "\\", False, True)
            sq = QuotedString("'", "\\", "\\", False, True)

            if drop_quotes:
                dq.setParseAction(lambda s: str(s[0]).strip('"'))
                sq.setParseAction(lambda s: str(s[0]).strip("'"))

            qs = dq | sq

            return qs

        # ------------------------------
        # Keywords
        # ------------------------------

        # Valid names of container object.  TODO: build from MWLibrary.xml
        # container_name = oneOf(" ".join(container_types))

        # Valid names of container object.  TODO: build from MWLibrary.xml
        # noncontainer_name = oneOf(" ".join(noncontainer_types))

        object_name = oneOf(" ".join(container_types + noncontainer_types))

        # Valid names of action objects.  TODO: build from MWLibrary.xml
        action_name = oneOf(" ".join(shorthand_action_types))

        # Allowed foreign languages
        language_name = Literal("python") | Literal("ruby")

        # ------------------------------
        # Values and Expressions
        # ------------------------------

        integer_number = Word(nums)('str')
        integer_number.setParseAction(lambda x: int(x.str))
        float_number = Combine(Word(nums) + Optional(Literal(".") + Word(nums)))('str')
        float_number.setParseAction(lambda x: float(x.str))
        time_unit = Literal("ms") | Literal("us") | Literal("s") | Literal("min")
        duration = Combine(integer_number + time_unit)
        identifier = Word(alphanums + '_' + '#')
        function_call = identifier("name") + arg_list_open + Group(delimitedList(expression))("args") + arg_list_close

        def function_call_helper(n, a):
            f_args = None
            if a is not None:
                f_args = a.asList()
            r = [MWFunctionCall(n, f_args)]
            return r

        function_call.setParseAction(lambda x: function_call_helper(x.name, x.args))

        array_reference = identifier('arr_var_ref_name') + index_operator_open + expression('arr_var_ref_index') + index_operator_close
        array_reference.setParseAction(lambda x: MWVariableReference(identifier=x.arr_var_ref_name, index=x.arr_var_ref_index))

        # for now, just support 1D array indexing.  Fancier slicing, etc. can come later
        #variable_index_argument = Suppress(arg_list_open) + (integer_number | variable_reference) + Suppress(arg_list_close)

        variable_reference = identifier("varname")
        variable_reference.setParseAction(lambda x: MWVariableReference(identifier=x.varname))

        # ------------------------------
        # Templates
        # ------------------------------

        simple_value_template = def_keyword + identifier("name") + Suppress(assign) + value("value")
        simple_value_template.setParseAction(lambda x: create_template_definition(x.name, [], children=[x.value]))
        template_reference = macro_symbol + identifier("name") + Optional(NotAny(LineEnd()) + Suppress("(") + ZeroOrMore(value + Suppress(Optional(",")))("args") + Suppress(")"))
        template_reference.setParseAction(lambda x: TemplateReference(x.name, x.args))

        macro_template_decl = def_keyword + identifier("name") + \
                              Optional(Suppress("(") + ZeroOrMore(identifier + Optional(Suppress(","))) + Suppress(")"))("args") + \
                              Optional(Suppress(assign)) + \
                              block(object_declaration, "body")

        macro_template_val = def_keyword + identifier("name") + \
                              Optional(Suppress("(") + ZeroOrMore(identifier + Optional(Suppress(","))) + Suppress(")"))("args") + \
                              Suppress(assign) + value("body")

        macro_template_decl.setParseAction(lambda x: create_template_definition(x.name, x.args, children=x.body))  # for now
        macro_template_val.setParseAction(lambda x: create_template_definition(x.name, x.args, children=x.body))  # for now

        template_definition = simple_value_template | macro_template_decl | macro_template_val

        # ------------------------------
        # Macro control flow
        # ------------------------------

        macro_if = macro_symbol + Suppress("if") + \
                   Suppress("(") + expression("condition") + Suppress(")") -\
                   block(object_declaration, "body") +\
                   Optional(Suppress("else") + \
                            block(object_declaration, "else_body"))

        macro_if.setParseAction(lambda x: TemplateIf(x.condition,
                                                     x.body,
                                                     x.else_body))

        macro_element = macro_if | macro_template_val

        # ------------------------------
        # Operators, infix notation, etc.
        # ------------------------------

        # Basic expression handling
        operand = (template_reference | duration | integer_number | float_number | quoted_string_fn(False) |
                   function_call | array_reference | variable_reference)

        exp_op = Literal("^") | Literal("**")
        sign_op = Literal("+") | Literal("-")
        multiply_op = Literal("*") | Literal("/")
        plus_op = Literal("+") | Literal("-")

        # operators + normalized optional syntax
        not_op = (Literal("not") | Literal("!")).setParseAction(lambda x: ["not"])
        and_op = (Literal("and") | Literal("&&")).setParseAction(lambda x: ["and"])
        or_op = (Literal("or") | Literal("||")).setParseAction(lambda x: ["or"])
        comp_op = list_to_literals([">=", "<=", ">", "<", "==", "!="])

        def binary_expression_helper(pr):

            assert(len(pr) >= 3)

            operator = pr[1]
            operand1 = pr[0]
            operand2 = pr[2]
            expr = MWBinaryExpression(operator, operand1, operand2)

            if len(pr) > 3:
                # why the f does pyparsing do this?
                return binary_expression_helper([expr] + pr[3:])
            else:
                return expr

        def unary_expression_helper(pr):
            operator = ""
            if len(pr) == 2:
                operator = pr[0]
                operand = pr[1]
            else:
                raise Exception("Incorrect number of operands to unary op: %s" % pr)

            return MWUnaryExpression(operator, operand)

        expression << operatorPrecedence(operand,
                                         [(exp_op, 2, opAssoc.RIGHT, lambda x: binary_expression_helper(x[0])),
                                          (sign_op, 1, opAssoc.RIGHT, lambda x: unary_expression_helper(x[0])),
                                          (multiply_op, 2, opAssoc.LEFT, lambda x: binary_expression_helper(x[0])),
                                          (plus_op, 2, opAssoc.LEFT, lambda x: binary_expression_helper(x[0])),
                                          (not_op, 1, opAssoc.RIGHT, lambda x: unary_expression_helper(x[0])),
                                          (or_op,  2, opAssoc.LEFT,  lambda x: binary_expression_helper(x[0])),
                                          (and_op, 2, opAssoc.LEFT,  lambda x: binary_expression_helper(x[0])),
                                          (comp_op, 2, opAssoc.LEFT, lambda x: binary_expression_helper(x[0]))
                                         ])

        value << (dummy_token("expression") | expression)

        # --------------------------------------------
        # Conditionals
        # --------------------------------------------

        cond_expr = expression

        conditional = (dummy_token("conditional expression") | cond_expr)

        # --------------------------------------------
        # Miscellaneous general reusable syntax parts
        # --------------------------------------------

        property_pair = Group(Word(alphanums + '_')("prop") + Suppress(assign) - value("value"))
        property_list = OneOrMore(property_pair + Optional(Suppress(",")))

        # ------------------------------
        # Object Declarations
        # ------------------------------

        # Actions
        action = Forward()

        generic_action = action_name("type") + arg_list_open + Optional(value)("arg") + Optional(property_list)("props") + arg_list_close
        generic_action.setParseAction(lambda a: Action(a.type,  a.arg, props=a.props))

        assignment_action = NotAny(def_keyword) + identifier("variable") + assign + value("value")
        assignment_action.setParseAction(lambda a: AssignmentAction(a.variable, a.value))

        if(use_significant_whitespace):
            foreign_code_action = language_name("lang") - "(" + \
                                  Regex(r"\s*\"\"\"\s*^(?P<padding>\s*)(?P<code>.*?)\s*\"\"\"", re.MULTILINE | re.DOTALL) + \
                                  ")"
        else:
            foreign_code_action = language_name("lang") + Regex(r"{\s*^(?P<padding>\s*)(?P<code>.*?)^\s*}", re.MULTILINE | re.DOTALL)

        foreign_code_action.setParseAction(lambda a: ForeignCodeAction(a.lang, remove_python_padding(a.code, a.padding)))

        if_action = Literal("if") + conditional("condition") + block(action, "children")
        if_action.setParseAction(lambda a: MWASTNode("action", props={"type": "if", "condition": a.condition}, children=a.children))

        action << (dummy_token("action") | macro_element | generic_action | assignment_action | foreign_code_action | if_action)

        # "Ordinary" components

        valid_tag = (quoted_string_fn(True) | template_reference)
        unquoted_tag = identifier

        std_obj_decl = ((
                         (object_name("obj_type") +         # "alt" syntax
                           unquoted_tag("tag") -
                           prop_list_open)

                          |                                   # OR

                          (object_name("obj_type") +          # "regular" syntax
                           prop_list_open -
                           Optional(valid_tag)("tag")) +
                           Optional(Suppress(","))

                         ) +

                         (Optional(property_list)("props") +  # remaining syntax
                          prop_list_close +
                          Optional(block(object_declaration, "children") +
                          LineEnd()))
                        )

        std_obj_decl.setParseAction(lambda c: MWASTNode(c.obj_type, c.tag,
                                                        props=nested_array_to_dict(c.props),
                                                        children=getattr(c, 'children', [])))

        transition = ((dummy_token("transition") | macro_element |
                        Literal("always") | conditional)("condition") -
                        Suppress("->") +
                        (dummy_token("transition target") |
                            quoted_string_fn() | template_reference | Literal("yield"))("target") +
                        LineEnd()
                     )

        transition.setParseAction(lambda t: Transition(t.condition, t.target))

        state_payload = None
        if use_significant_whitespace:
            state_payload = block_open + indentedBlock(action_list_marker + block(action, "actions") + \
                            transition_list_marker + block(transition, "transitions"), self.indent_stack, True)
        else:
            state_payload = block(action, "actions") + transition_list_marker + block(transition, "transitions")

        state = Literal("state") - \
                prop_list_open + \
                Optional(valid_tag)("tag") + Optional(Suppress(",")) + Optional(property_list)("props") + \
                prop_list_close + \
                state_payload

        state.setParseAction(lambda s: State(s.tag, props=s.props, actions=s.actions, transitions=s.transitions))

        # ------------------------------
        # Variable Declarations
        # ------------------------------

        variable_declaration = LineStart() + Literal("var") - identifier("tag") + Optional(assign + value("default"))
        variable_declaration.setParseAction(lambda x: MWASTNode("variable", x.tag, props={'default': x.default}))

        # ----------------------------------------------------
        # Top-level object declarations and aliases thereof
        # ----------------------------------------------------

         # an in-place quicky
        def alias_parse_action(x):
            if x.alias != '':
                x.object.props['alias'] = x.alias
            return x.object

        ordinary_object_declaration = Optional(identifier("alias") + assign) + (std_obj_decl |
                                                                                action | state)("object")
        ordinary_object_declaration.setParseAction(alias_parse_action)

        object_declaration << (macro_if | template_definition | template_reference | ordinary_object_declaration | variable_declaration)

        # --------------------------------------
        # Final assembly into a "master" parser
        # --------------------------------------

        self.parser = OneOrMore(object_declaration) + StringEnd()
        self.parser.enablePackrat()

        # ------------------------------
        # Comment preprocesser (used separately)
        # ------------------------------

        comment_regex = r"(//|#).*?$"  # accept either shell or c++ style comments
        self.comment_parser = (QuotedString('"', unquoteResults=False) |
                               QuotedString("'", unquoteResults=False) |
                               Suppress(Regex(comment_regex, re.MULTILINE | re.DOTALL)))

    def parse_string(self, s, process_templates=True):
        """Process a string containing valid MWX content, and return a tree of
           MWASTNode objects
        """
        uncommented = self.comment_parser.transformString(s)

        try:
            results = self.parser.parseString(uncommented, parseAll=True)

        except ParseBaseException, pe:
            print_parser_error(pe, s)
            exit()

        if process_templates:
            results = resolve_templates(results)

        results = do_registered_rewrites(results)

        if getattr(results, '__iter__', False):
            results = RootNode(children=results)

        return results


class MWXMLParser:
    """A simple parser for processing MW XML format"""

    def __init__(self):
        self.handlers = {}

    def xml_element_to_ast(self, element):
        """Converts an xml element to an MWASTNode"""
        props = {}
        children = []

        for key in element.keys():
            props[key] = element.get(key)

        for child in element.getchildren():
            children.append(self.xml_element_to_ast(child))

        return MWASTNode(element.tag, element.get('tag'),
                         props=deepcopy(props), children=children)

    def parse_string(self, s, process_templates=True):
        """Process a string containing MW XML, and return a tree of MWASTNode
           objects
        """
        from xml.etree import ElementTree

        # TODO: error checking
        xml_root = ElementTree.fromstring(s)

        mwtree = []

        for element in xml_root:
            mwtree.append(self.xml_element_to_ast(element))

        root_node = RootNode(children=mwtree)

        return_tree = root_node

        if process_templates:
            template_engine = TemplateTreeRewriter(root_node)
            return_tree = template_engine.rewrite_tree()

        return_tree = do_registered_xml_import_rewrites(return_tree)

        return return_tree
