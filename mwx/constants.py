import re

# TODO: read these from MW itself

container_types = ['experiment', 'protocol', 'block', 'trial', 'protocol',
                   'task_system', 'io_device', 'iodevice',
                   'stimulus_group', 'range_replicator']

selection_types = container_types + ['selection_variable']

noncontainer_types = ['stimulus',
                      'variable',
                      'selection_variable',
                      'channel',
                      'sound',
                      'action']


class MWProperty(object):

    def __init__(self, name, field_type):
        self.name = name
        self.type = field_type

    def __str__(self):
        return self.name

    def convert_to_mwx(self, s):
        return self.type.convert_to_mwx(s)

    def __hash__(self):
        return self.name.__hash__()

    def __eq__(self, other):
        return self.name == other


def quoted_string(s):
    return '"s"'


def optionally_quoted_string(s):
    if re.search(r'\s', s):
        return '"%s"' % s
    else:
        return s

class MWType(object):

    def __init__(self, name, interpret_fn=optionally_quoted_string):
        self.name = name
        self.interpret_fn = interpret_fn

    def convert_to_mwx(self, s):
        return self.interpret_fn(s)

mw_string = MWType('string', quoted_string)
mw_time = MWType('time')
mw_expression = MWType('expression', str)
mw_stimulus = MWType('stimulus')
mw_selection = MWType('selection')
mw_iodevice = MWType('iodevice')
mw_sound = MWType('sound')

# action types that can be displayed using shorthand
# dictionary type -> primary arg
shorthand_actions = {'wait':                          MWProperty('duration', mw_time),
                     'report':                        MWProperty('message', mw_string),
                     'update_stimulus_display':       None,
                     'bring_stimulus_to_front':       MWProperty('stimulus', mw_stimulus),
                     'send_stimulus_to_back':         MWProperty('stimulus', mw_stimulus),
                     'live_queue_stimulus':           MWProperty('stimulus', mw_stimulus),
                     'queue_stimulus':                MWProperty('stimulus', mw_stimulus),
                     'dequeue_stimulus':              MWProperty('stimulus', mw_stimulus),
                     'play_sound':                    MWProperty('sound', mw_sound),
                     'if':                            MWProperty('condition', mw_expression),
                     'start_device_io':               MWProperty('device', mw_iodevice),
                     'stop_device_io':                MWProperty('device', mw_iodevice),
                     'accept_selections':             MWProperty('selection', mw_selection),
                     'reject_selections':             MWProperty('selection', mw_selection),
                     'reset_selections':              MWProperty('selection', mw_selection)}

shorthand_action_types = shorthand_actions.keys()


type_aliases = {'state':      'task_system_state',
                'channel':    'iochannel'}


reverse_type_aliases = dict(zip(type_aliases.values(), type_aliases.keys()))
