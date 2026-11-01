from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase
from insuree.apps import InsureeConfig
from insuree.test_helpers import generate_random_insuree_number


class CountryFixtureHelperTest(SimpleTestCase):
    def test_egypt_fixture_number_matches_dob_and_gender(self):
        with patch.object(InsureeConfig, 'insuree_number_validator', 'egypt_localization.validators.fixture'):
            for birthday in [date(1972, 8, 9), date(2001, 2, 3), '2015-06-20', datetime(1990, 1, 1)]:
                expected = birthday.date() if isinstance(birthday, datetime) else date.fromisoformat(birthday) if isinstance(birthday, str) else birthday
                for gender in ['M', 'F', SimpleNamespace(code='F')]:
                    with self.subTest(birthday=expected, gender=gender):
                        value = generate_random_insuree_number(birthday, gender)
                        self.assertEqual(len(value), 14)
                        self.assertTrue(value.isdigit())
                        century = 1900 if value[0] == '2' else 2000
                        observed = date(century + int(value[1:3]), int(value[3:5]), int(value[5:7]))
                        self.assertEqual(observed, expected)
                        self.assertEqual(value[7:9], '01')
                        code = getattr(gender, 'code', gender)
                        self.assertEqual(int(value[12]) % 2, 0 if code == 'F' else 1)

    def test_invalid_birthdate_is_not_silently_replaced(self):
        with patch.object(InsureeConfig, 'insuree_number_validator', 'egypt_localization.validators.fixture'):
            with self.assertRaises(ValueError):
                generate_random_insuree_number('2001-02-30', 'F')
            with self.assertRaises(ValueError):
                generate_random_insuree_number(date(1800, 1, 1), 'M')

    def test_generic_country_generation_remains_the_same_contract(self):
        with patch.object(InsureeConfig, 'insuree_number_validator', None), patch.object(InsureeConfig, 'insuree_number_max_length', 5), patch('insuree.test_helpers.random.randrange', return_value=12345) as rand:
            self.assertEqual(generate_random_insuree_number(), 12345)
            rand.assert_called_once_with(10000, 99999)
