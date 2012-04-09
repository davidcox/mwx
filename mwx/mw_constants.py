# TODO: read these from MW itself

container_types = ["experiment", "protocol", "block", "trial", "protocol",
                   "task_system"]

noncontainer_types = ["stimulus",
                      "variable",
                      "selection_variable",
                      "io_device"]


# action types that can be displayed using shorthand
# dictionary type -> primary arg
shorthand_actions = {"wait":                "duration",
                     "report":              "message",
                     "update_display":      None,
                     "queue_stimulus":      "stimulus",
                     "dequeue_stimulus":    "stimulus",
                     "if":                  "condition",
                     "start_device_io":     "device",
                     "stop_device_io":      "device"}

shorthand_action_types = shorthand_actions.keys()
