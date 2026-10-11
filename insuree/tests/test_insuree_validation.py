from django.test import TestCase

from insuree.apps import InsureeConfig
from insuree.services import validate_insuree_number


def fail1(x):
    if x == "fail1":
        return ["fail1"]
    else:
        return []


class InsureeValidationTest(TestCase):
    def test_validator(self):

        InsureeConfig.insuree_number_validator = 'insuree.tests.test_insuree_validation.fail1'
        InsureeConfig.insuree_number_max_length = None
        InsureeConfig.insuree_number_min_length = None
        InsureeConfig.insuree_number_modulo_root = None
        
        self.assertEqual(validate_insuree_number(None), [])
        self.assertEqual(validate_insuree_number("valid"), [])
        self.assertEqual(validate_insuree_number("fail1"), ["fail1"])
        InsureeConfig. insuree_number_validator = None
        InsureeConfig.insuree_number_max_length = None
        InsureeConfig.insuree_number_min_length = None
        InsureeConfig.insuree_number_modulo_root = None
        
        self.assertEqual(validate_insuree_number(None), [])
        self.assertEqual(validate_insuree_number("valid"), [])
        self.assertEqual(validate_insuree_number("fail1"), [])

    def test_len(self):
        InsureeConfig. insuree_number_validator = None
        InsureeConfig.insuree_number_max_length = 5
        InsureeConfig.insuree_number_min_length = 5
        InsureeConfig.insuree_number_modulo_root = None
        
        self.assertEqual(len(validate_insuree_number(None)), 1)
        self.assertEqual(len(validate_insuree_number("")), 1)
        self.assertEqual(len(validate_insuree_number("foo")), 1)
        self.assertEqual(len(validate_insuree_number("12345")), 0)
        self.assertEqual(len(validate_insuree_number("1234567")), 1)
        InsureeConfig. insuree_number_validator = None
        InsureeConfig.insuree_number_max_length = 7
        InsureeConfig.insuree_number_min_length = 7
        InsureeConfig.insuree_number_modulo_root = None
        
        self.assertEqual(len(validate_insuree_number("12345")), 1)
        self.assertEqual(len(validate_insuree_number("1234567")), 0)

    def test_mod(self):
        InsureeConfig. insuree_number_validator = None
        InsureeConfig.insuree_number_max_length = 5
        InsureeConfig.insuree_number_min_length = 5
        InsureeConfig.insuree_number_modulo_root = 7
        
        self.assertEqual(len(validate_insuree_number(None)), 1)
        self.assertEqual(len(validate_insuree_number("12342")), 0)
        self.assertEqual(len(validate_insuree_number("12345")), 1)
        self.assertEqual(len(validate_insuree_number("1234567")), 1)
        InsureeConfig. insuree_number_validator = None
        InsureeConfig.insuree_number_max_length = 7
        InsureeConfig.insuree_number_min_length = 7
        InsureeConfig.insuree_number_modulo_root = 5
        
        self.assertEqual(len(validate_insuree_number("12345")), 1)
        self.assertEqual(len(validate_insuree_number("1234561")), 0)
        self.assertEqual(len(validate_insuree_number("1234560")), 1)


from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from insuree.models import InsureeStatus
from insuree.services import validate_insuree


class DuplicateNationalIdValidationTest(SimpleTestCase):
    """Read-only regressions; no beneficiary rows are created by this suite."""

    NUMBER = "28803120134518"  # approved synthetic Scenario A identifier
    OTHER_UUID = "10000000-0000-4000-8000-000000000001"
    SELF_UUID = "20000000-0000-4000-8000-000000000002"
    TAKEN_CODE = 1

    def setUp(self):
        self.validator_config = patch.object(InsureeConfig, "insuree_number_validator", "egypt.test.validator")
        self.validator_config.start()
        self.addCleanup(self.validator_config.stop)
        format_patcher = patch("insuree.services.custom_insuree_number_validation", return_value=[])
        self.format_check = format_patcher.start()
        self.addCleanup(format_patcher.stop)
        model_patcher = patch("insuree.services.Insuree")
        self.insuree_model = model_patcher.start()
        self.addCleanup(model_patcher.stop)
        self.matches = self.insuree_model.objects.filter.return_value
        self.matches.filter.return_value.exists.return_value = False
        self.matches.exists.return_value = False

    def test_new_unique_id_is_valid_after_format_check(self):
        self.assertEqual(validate_insuree_number(self.NUMBER), [])
        self.format_check.assert_called_once_with(self.NUMBER)
        self.insuree_model.objects.filter.assert_called_once_with(chf_id=self.NUMBER)

    def test_active_duplicate_is_rejected_without_personal_details(self):
        self.matches.filter.return_value.exists.return_value = True
        errors = validate_insuree_number(self.NUMBER)
        self.assertEqual(errors, [{"errorCode": InsureeConfig.validation_code_taken_insuree_number,
                                   "message": "الرقم القومي مسجل بالفعل و نشط"}])
        self.matches.filter.assert_called_once_with(validity_to__isnull=True, status=InsureeStatus.ACTIVE)
        self.assertNotIn(self.NUMBER, errors[0]["message"])

    def test_inactive_or_historical_duplicate_is_rejected(self):
        self.matches.exists.return_value = True
        errors = validate_insuree_number(self.NUMBER)
        self.assertEqual(errors, [{"errorCode": InsureeConfig.validation_code_taken_insuree_number,
                                   "message": "الرقم القومي مسجل بالفعل لكن غير نشط"}])

    def test_self_edit_excludes_current_row_and_its_historical_snapshots(self):
        current = SimpleNamespace(uuid=self.SELF_UUID, id=42)
        self.insuree_model.objects.filter.side_effect = lambda **kw: (
            SimpleNamespace(first=lambda: current) if "uuid" in kw else self.matches
        )
        remainder = self.matches.exclude.return_value
        remainder.filter.return_value.exists.return_value = False
        remainder.exists.return_value = False
        self.assertEqual(validate_insuree_number(self.NUMBER, self.SELF_UUID), [])
        self.insuree_model.objects.filter.assert_any_call(uuid=self.SELF_UUID, validity_to__isnull=True)
        exclusion = self.matches.exclude.call_args.args[0]
        self.assertIn(self.SELF_UUID, str(exclusion))
        self.assertIn("legacy_id", str(exclusion))
        self.assertIn("42", str(exclusion))

    def test_same_uuid_edit_allows_inactive_current_record_and_its_history(self):
        current = SimpleNamespace(uuid=self.SELF_UUID, id=42, status=InsureeStatus.INACTIVE)
        self.insuree_model.objects.filter.side_effect = lambda **kw: (
            SimpleNamespace(first=lambda: current) if "uuid" in kw else self.matches
        )
        remainder = self.matches.exclude.return_value
        remainder.filter.return_value.exists.return_value = False
        remainder.exists.return_value = False
        self.assertEqual(validate_insuree_number(self.NUMBER, self.SELF_UUID), [])

    def test_different_record_uuid_does_not_exempt_the_duplicate(self):
        current = SimpleNamespace(uuid=self.OTHER_UUID, id=19)
        self.insuree_model.objects.filter.side_effect = lambda **kw: (
            SimpleNamespace(first=lambda: current) if "uuid" in kw else self.matches
        )
        self.matches.exclude.return_value.filter.return_value.exists.return_value = True
        errors = validate_insuree_number(self.NUMBER, self.OTHER_UUID)
        self.assertEqual(errors[0]["message"], "الرقم القومي مسجل بالفعل و نشط")

    def test_format_failure_wins_and_does_not_query_duplicate_records(self):
        self.format_check.return_value = [{"errorCode": 901, "message": "Egyptian ID format error"}]
        self.assertEqual(validate_insuree_number("invalid"), self.format_check.return_value)
        self.insuree_model.objects.filter.assert_not_called()

    def test_create_mutation_validation_rejects_duplicate_instead_of_succeeding(self):
        self.matches.filter.return_value.exists.return_value = True
        candidate = SimpleNamespace(chf_id=self.NUMBER, uuid=self.OTHER_UUID)
        with self.assertRaisesMessage(ValidationError, "الرقم القومي مسجل بالفعل و نشط") as caught:
            validate_insuree(candidate)
        self.assertNotIn(self.NUMBER, str(caught.exception))

    def test_format_failure_keeps_original_mutation_error_contract(self):
        self.format_check.return_value = [{"errorCode": 901, "message": "Egyptian ID format error"}]
        candidate = SimpleNamespace(chf_id="invalid", uuid=self.OTHER_UUID)
        with self.assertRaisesMessage(ValidationError, "invalid_insuree_number"):
            validate_insuree(candidate)

    def test_duplicate_is_still_checked_without_custom_format_validator(self):
        with patch.object(InsureeConfig, "insuree_number_validator", None), \
             patch.object(InsureeConfig, "insuree_number_max_length", None), \
             patch.object(InsureeConfig, "insuree_number_min_length", None), \
             patch.object(InsureeConfig, "insuree_number_modulo_root", None):
            self.matches.exists.return_value = True
            self.assertEqual(validate_insuree_number(self.NUMBER)[0]["message"],
                             "الرقم القومي مسجل بالفعل لكن غير نشط")
            self.format_check.assert_not_called()

    def test_identifier_search_can_validate_format_without_duplicate_rejection(self):
        self.matches.filter.return_value.exists.return_value = True
        self.assertEqual(validate_insuree_number(self.NUMBER, check_uniqueness=False), [])
        self.insuree_model.objects.filter.assert_not_called()


class GraphQLValidityContractTest(SimpleTestCase):
    def test_edit_uuid_is_optional_and_forwarded_to_service(self):
        import graphene
        from insuree.schema import Query

        field = Query._meta.fields["insuree_number_validity"]
        self.assertIn("insuree_uuid", field.args)
        self.assertNotIsInstance(field.args["insuree_uuid"].type, graphene.NonNull)

        info = SimpleNamespace(context=SimpleNamespace(user=SimpleNamespace(has_perms=lambda _: True)))
        with patch("insuree.schema.validate_insuree_number", return_value=[]) as validate:
            result = Query.resolve_insuree_number_validity(None, info, insuree_number="28803120134518")
            self.assertTrue(result.is_valid)
            validate.assert_called_once_with("28803120134518", insuree_uuid=None)

        with patch("insuree.schema.validate_insuree_number", return_value=[{
            "errorCode": 1, "message": "الرقم القومي مسجل بالفعل و نشط"
        }]) as validate:
            result = Query.resolve_insuree_number_validity(
                None, info, insuree_number="28803120134518", insuree_uuid=DuplicateNationalIdValidationTest.SELF_UUID
            )
            self.assertFalse(result.is_valid)
            self.assertEqual(result.error_message, "الرقم القومي مسجل بالفعل و نشط")
            validate.assert_called_once_with(
                "28803120134518", insuree_uuid=DuplicateNationalIdValidationTest.SELF_UUID
            )
