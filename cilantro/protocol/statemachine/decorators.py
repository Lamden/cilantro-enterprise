import cilantro.protocol.statemachine.state
from cilantro.logger import get_logger
import inspect

"""
This file implements and describes the various decorators used by States and StateMachines.  
"""


"""
----------------------------------------
Input Decorators
----------------------------------------

Input decorators allow states to define logic for incoming messages from the ReactorDaemon. These messages can be
envelopes from other actors, or timeout callbacks from unreceived replies.

# TODO more explanations
# TODO examples of how to use input decorators
"""


class StateInput:
    """
    A grouping of constants
    """
    INPUT = '_route_input'
    REQUEST = '_route_request'
    TIMEOUT = '_route_timeout'
    LOOKUP_FAILED = '_lookup_failed'

    ALL = [INPUT, REQUEST, TIMEOUT, LOOKUP_FAILED]


def input(msg_type):
    def decorate(func):
        # func._recv = msg_type
        setattr(func, StateInput.INPUT, msg_type)
        return func
    return decorate


def input_request(msg_type):
    def decorate(func):
        # func._reply = msg_type
        setattr(func, StateInput.REQUEST, msg_type)
        return func
    return decorate


def input_timeout(msg_type):
    def decorate(func):
        # func._timeout = msg_type
        setattr(func, StateInput.TIMEOUT, msg_type)
        return func
    return decorate


"""
----------------------------------------
State Timeout Decorator
----------------------------------------
"""

class StateTimeout:
    TIMEOUT_FLAG = '_state_timeout_flag'
    TIMEOUT_DUR = '_state_timeout_duration'


def timeout_after(timeout: int):

    def decorate(func):
        setattr(func, StateTimeout.TIMEOUT_FLAG, True)
        setattr(func, StateTimeout.TIMEOUT_DUR, timeout)

        return func

    return decorate


"""
----------------------------------------
Transition Decorators
----------------------------------------

Transition decorators allow states to define logic surrounding state transitions. Methods can be decorated to execute
some code whenever the defining state is transition into from another state, using enter_state(...), or transitioned
out of into another state, using exit_state(....).

For either decorator enter_state(...)/exit_state(...), if no arguement is specified then that method will act as a
'wildcard' and be called for ALL transitions, unless the state has another method that is decorated to handle a
a particular state.

# TODO clearer explanation
# TODO examples
"""
log = get_logger("StateMeta (Compile Time)")


# Internal constant for capturing all states using @enter_state and @exit_state decorators
ALL_STATES = 'ALL_STATES'


class StateTransition:
    ENTER = '_enter'
    EXIT = '_exit'

    ENTER_ANY = '_enter_any_state'
    EXIT_ANY = '_exit_any_state'

    ACCEPT_ALL = '_ACCEPT_ALL_STATES'

    _ANY_MAPPING = {ENTER: ENTER_ANY, EXIT: EXIT_ANY}

    @classmethod
    def get_any_attr(cls, trans_attr):
        assert trans_attr in cls._ANY_MAPPING, "can only fetch the 'any transition' attribute from enter or exit"
        return cls._ANY_MAPPING[trans_attr]


def _set_state_registry(func, attr_name, states):
    registry = []

    for s in states:
        # assert issubclass(s, cilantro.protocol.statemachine.state.State), \
        #     "Transition func decorator arg {} must be a State subclass".format(s)

        # Cast classes to names where necessary
        if inspect.isclass(s):
            s = s.__name__

        registry.append(s)

    setattr(func, attr_name, registry)
    return func


def enter_from(*args):
    def decorate(func):
        return _set_state_registry(func, StateTransition.ENTER, args)
    return decorate


def enter_from_any(func):
    setattr(func, StateTransition.ENTER, StateTransition.ACCEPT_ALL)
    return func


def exit_to(*args):
    def decorate(func):
        return _set_state_registry(func, StateTransition.EXIT, args)
    return decorate


def exit_to_any(func):
    setattr(func, StateTransition.EXIT, StateTransition.ACCEPT_ALL)
    return func
