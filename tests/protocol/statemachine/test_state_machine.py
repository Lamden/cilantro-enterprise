from cilantro.protocol.statemachine import StateMachine, State
from unittest import TestCase


"""
This stuff is a little tricky to test. In interest of optimizing utility per unit of time, we just create a toy example 
StateMachine class, with toy states, and use this in our test cases. 
The proper way to do this would prolly be to mock all this stuff, but that would be hella tedious.  
"""

DEFAULT_LIFT = None
DEFAULT_WEIGHT = 0

class SleepState(State):
    def reset_attrs(self):
        pass

    def enter(self, prev_state, *args, **kwargs):
        pass

    def exit(self, next_state, *args, **kwargs):
        pass

    def run(self):
        pass


class CodeState(State):
    def reset_attrs(self):
        self.lang = None
        self.activity = None

    def enter(self, prev_state, *args, **kwargs):
        pass

    def exit(self, next_state, *args, **kwargs):
        pass

    def run(self):
        pass


class LiftState(State):
    BENCH, SQUAT, DEADLIFT = 'BENCH', 'SQUAT', 'DEAD LIFT'

    def reset_attrs(self):
        self.current_lift = DEFAULT_LIFT
        self.current_weight = DEFAULT_WEIGHT

    def enter(self, prev_state, lift=DEFAULT_LIFT, weight=DEFAULT_WEIGHT):
        self.log.debug("Entering state with lift {} and weight {}".format(lift, weight))
        self.current_weight = weight
        self.current_lift = lift

    def exit(self, next_state, *args, **kwargs):
        pass

    def run(self):
        pass

    def lift(self):
        self.log.debug("Doing lift: {} ... with weight: {}".format(self.current_lift, self.current_weight))


class StuMachine(StateMachine):
    _INIT_STATE = SleepState
    _STATES = [SleepState, CodeState, LiftState]


class StateMachineTest(TestCase):

    def test_start(self):
        """
        Tests that a state machine starts, and enter the desired boot state
        """
        sm = StuMachine()

        sm.start()

        self.assertTrue(type(sm.state) is SleepState)

    def test_transition(self):
        """
        Tests that a state machine transitions into the correct state when instructed to do so
        """
        sm = StuMachine()

        sm.start()

        sm.transition(LiftState)

        self.assertTrue(type(sm.state) is LiftState)

    def test_transition_args(self):
        """
        Tests transitioning into a state with args produced to intended effect
        """
        sm = StuMachine()

        sm.start()

        lift = LiftState.SQUAT
        weight = 9000

        sm.transition(LiftState, lift=lift, weight=weight)

        self.assertTrue(type(sm.state) is LiftState)
        self.assertEqual(sm.state.current_lift, lift)
        self.assertEqual(sm.state.current_weight, weight)

    def test_transition_resets_attrs(self):
        """
        Tests that attributes are reset when a state is transitioned into
        """
        sm = StuMachine()

        sm.start()

        lift = LiftState.SQUAT
        weight = 9000

        sm.transition(LiftState, lift=lift, weight=weight)

        self.assertTrue(type(sm.state) is LiftState)
        self.assertEqual(sm.state.current_lift, lift)
        self.assertEqual(sm.state.current_weight, weight)

        sm.transition(CodeState)

        self.assertTrue(type(sm.state) is CodeState)

        sm.transition(LiftState)

        self.assertTrue(type(sm.state) is LiftState)
        self.assertEqual(sm.state.current_lift, DEFAULT_LIFT)
        self.assertEqual(sm.state.current_weight, DEFAULT_WEIGHT)
