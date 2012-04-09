import logging
import copy

class MockComponentRegistry(object):
    """A mock MW component registry object, for testing without requiring the
       entire binary infrastructure of MWorks"""

    def __init__(self):
        self.reg = {}

    def create(self, mw_type, tag, params):
        """Create and register a new MW component"""

        logging.debug("CREATE: [%s], [%s], %s" % (mw_type, tag, params))

        params['type'] = mw_type
        params['children'] = []
        params['instance_count'] = 0
        self.reg[tag] = params

    def lookup(self, tag):
        """Find an existing MW component by tag name"""
        if tag in self.reg:
            obj = self.reg[tag]
        else:
            obj = None

        return obj

    def connect(self, parent, child):
        """Connect one MW component to another"""

        logging.debug("CONNECT: [%s] to [%s]" % (child, parent))

        obj = self.lookup(parent)

        if obj is None:
            raise Exception(("Attempt to connect child %s to invalid " +\
                            "parent obj: %s") % (child, parent))

        obj['children'].append(child)

    def create_instance(self, tag):
        """Create an 'instance' of an MW paradigm component.  This content,
           'instance' reference to a copy of the object which carries its
           own indpependent local variable context"""
        obj = self.reg[tag]
        count = obj['instance_count']
        obj2 = copy.copy(obj)

        new_tag = '%s%d' % (tag, count)
        self.reg[new_tag] = obj2

    def finalize(self, tag):
        logging.debug("FINALIZE: %s" % tag)

    def __str__(self):
        return str(self.reg)
