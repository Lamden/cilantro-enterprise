from unittest import TestCase
from cilantro_ee.messages.formatting import primatives


class TestFormatting(TestCase):
    def test_dict_has_keys_true(self):
        good_dict = {'a': 1, 'b': 2}

        self.assertTrue(primatives.dict_has_keys(good_dict, {'a', 'b'}))

    def test_dict_has_keys_false(self):
        bad_dict = {'a': 1, 'b': 2}

        self.assertFalse(primatives.dict_has_keys(bad_dict, {'a', 'x'}))

    def test_dict_has_keys_false_other_dict(self):
        bad_dict = {'a': 1, 'b': 2, 'x': 5}

        self.assertFalse(primatives.dict_has_keys(bad_dict, {'a', 'x'}))

    def test_identifier_is_formatted_passes(self):
        self.assertTrue(primatives.identifier_is_formatted('hello_there'))

    def test_identifier_starts_with_underscore_fails(self):
        self.assertFalse(primatives.identifier_is_formatted('_hello_there'))

    def test_identifier_not_string_fails(self):
        self.assertFalse(primatives.identifier_is_formatted(None))

    def test_contract_name_is_formatted_passes(self):
        self.assertTrue(primatives.contract_name_is_formatted('con_hello_there'))

    def test_contract_name_starts_with_underscore_fails(self):
        self.assertFalse(primatives.contract_name_is_formatted('_con_hello_there'))

    def test_contract_name_not_starting_with_con_fails(self):
        self.assertFalse(primatives.contract_name_is_formatted('hello_there'))

    def test_contract_name_not_string_fails(self):
        self.assertFalse(primatives.contract_name_is_formatted(None))

    def test_vk_formatted_passes(self):
        self.assertTrue(primatives.vk_is_formatted('a' * 64))

    def test_vk_too_long_fails(self):
        self.assertFalse(primatives.vk_is_formatted('a' * 65))

    def test_vk_too_short_fails(self):
        self.assertFalse(primatives.vk_is_formatted('a' * 63))

    def test_vk_not_hex_fails(self):
        self.assertFalse(primatives.vk_is_formatted('x' * 64))

    def test_vk_not_string_fails(self):
        self.assertFalse(primatives.signature_is_formatted(123))

    def test_signature_formatted_passes(self):
        self.assertTrue(primatives.signature_is_formatted('a' * 128))

    def test_signature_too_long_fails(self):
        self.assertFalse(primatives.signature_is_formatted('a' * 1234))

    def test_signature_too_short_fails(self):
        self.assertFalse(primatives.signature_is_formatted('a' * 12))

    def test_signature_not_hex_fails(self):
        self.assertFalse(primatives.signature_is_formatted('x' * 128))

    def test_signature_not_string_fails(self):
        self.assertFalse(primatives.signature_is_formatted(123))

    def test_number_is_formatted_passes(self):
        self.assertTrue(primatives.number_is_formatted(1))

    def test_neg_number_fails(self):
        self.assertFalse(primatives.number_is_formatted(-1))

    def test_non_number_fails(self):
        self.assertFalse(primatives.number_is_formatted('1'))

    def test_kwargs_formatted_passes(self):
        d = {
            'asdf': 12,
            'Aghe': 44,
            'hello_there': 267
        }

        self.assertTrue(primatives.kwargs_are_formatted(d))

    def test_kwargs_not_identifier_types_fails(self):
        d = {
            True: 12,
            'Aghe': 44,
            'hello_there': 267
        }

        self.assertFalse(primatives.kwargs_are_formatted(d))

    def test_kwargs_not_formatted_fails(self):
        d = {
            '_asdf': 12,
            'Aghe': 44,
            'hello_there': 267
        }

        self.assertFalse(primatives.kwargs_are_formatted(d))