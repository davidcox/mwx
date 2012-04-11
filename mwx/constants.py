# TODO: read these from MW itself

container_types = ['experiment', 'protocol', 'block', 'trial', 'protocol',
                   'task_system']

selection_types = container_types + ['selection_variable']

noncontainer_types = ['stimulus',
                      'variable',
                      'selection_variable',
                      'io_device']


# action types that can be displayed using shorthand
# dictionary type -> primary arg
shorthand_actions = {'wait':                          'duration',
                     'report':                        'message',
                     'update_stimulus_display':       None,
                     'bring_stimulus_to_front':       'stimulus',
                     'send_stimulus_to_back':         'stimulus',
                     'live_queue_stimulus':           'stimulus',
                     'queue_stimulus':                'stimulus',
                     'dequeue_stimulus':              'stimulus',
                     'play_sound':                    'sound',
                     'if':                            'condition',
                     'start_device_io':               'device',
                     'stop_device_io':                'device',
                     'accept_selections':             'selection',
                     'reject_selections':             'selection',
                     'reset_selections':              'selection'}

shorthand_action_types = shorthand_actions.keys()


type_aliases = {'state':      'task_system_state',
                'channel':    'iochannel'}


reverse_type_aliases = dict(zip(type_aliases.values(), type_aliases.keys()))
