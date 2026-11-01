from insuree.apps import InsureeConfig
from insuree.models import Insuree, Family, Gender, InsureePhoto, Profession, Education, Relation, ConfirmationType, FamilyType, IdentificationType
from insuree.services import validate_insuree_number
from location.models import Location
from location.test_helpers import create_test_village

import random
import re
from datetime import datetime, date
from core import filter_validity
    
def egypt_fixture_validation_enabled():
    from django.apps import apps
    if not apps.is_installed("egypt_localization"):
        return False
    from egypt_localization.signals import _enforcement_enabled
    return _enforcement_enabled()


def validate_test_fixture_number(number):
    if egypt_fixture_validation_enabled():
        # This is the same strict formatter used by the active model signal;
        # app configuration can be unseeded before the test database is selected.
        from egypt_localization.validators import validate_egyptian_national_id_for_insuree
        errors = validate_egyptian_national_id_for_insuree(str(number))
        if not errors and Insuree.objects.filter(chf_id=number).exists():
            return ["duplicate test fixture number"]
        return errors
    return validate_insuree_number(number)


def generate_random_insuree_number(birth_date=None, gender=None):
    # Test fixtures must honour the configured country validator without disabling
    # its model signal. This helper is not used by production enrolment writes.
    if egypt_fixture_validation_enabled():
        birthday = birth_date or date(1972, 8, 9)
        if isinstance(birthday, str):
            birthday = datetime.fromisoformat(birthday).date()
        elif isinstance(birthday, datetime):
            birthday = birthday.date()
        if not isinstance(birthday, date) or not 1900 <= birthday.year <= 2099:
            raise ValueError("Egyptian test fixture requires a supported birth date")
        code = str(getattr(gender, "code", gender) or "M").upper()
        parity = 0 if code == "F" else 1
        serial = random.randrange(1, 5000) * 2 + parity
        century = "2" if birthday.year < 2000 else "3"
        return century + birthday.strftime("%y%m%d") + "01" + str(serial).zfill(4) + "0"
    start_number = pow(10, (InsureeConfig.insuree_number_max_length or 8) - 1)
    end_number = start_number * 10 - 1
    return random.randrange(start_number, end_number)
    
def create_test_insuree(with_family=True, is_head=False, custom_props=None, family_custom_props=None):
    create_test_gender()
    create_test_profession()
    create_test_education()
    create_test_relation()
    create_test_confirmation_type()
    create_test_family_type()

    if custom_props is None:
        custom_props = {}
    else:
        custom_props = {k: v for k, v in custom_props.items() if hasattr(Insuree, k)}
    if family_custom_props is None:
        family_custom_props = {}
  
        
    # insuree has a mandatory reference to family and family has a mandatory reference to insuree
    # So we first insert the family with a dummy id and then update it
    #loof if it exists
    family = None
    location = None
    village = None
    insuree = None
    if 'id' in custom_props:
        insuree = Insuree.objects.filter(id=custom_props['id'], *Insuree.filter_validity()).first()
    if not insuree and 'uuid' in custom_props:
        insuree = Insuree.objects.filter(uuid=custom_props['uuid'], *Insuree.filter_validity()).first()
    if not insuree:
        egypt_fixture = egypt_fixture_validation_enabled()
        birthday = custom_props.get("dob", date(1972, 8, 9))
        gender = custom_props.get("gender", Gender.objects.get(code="M"))
        if egypt_fixture:
            if isinstance(birthday, str):
                birthday = datetime.fromisoformat(birthday).date()
            elif isinstance(birthday, datetime):
                birthday = birthday.date()
            custom_props["dob"] = birthday
        if 'chf_id' in custom_props:
            ref = custom_props.pop('chf_id')
        else:
            ref = generate_random_insuree_number(birthday, gender)
        while validate_test_fixture_number(ref) != []:
            ref = generate_random_insuree_number(birthday, gender)
        insuree = Insuree.objects.filter(chf_id=ref, validity_to__isnull=True).first()
    if insuree is None:
        #managing location
        family_location = None
        if  isinstance(family_custom_props, dict):
            if "location" in family_custom_props:
                family_location = family_custom_props['location']
            elif "location_id" in family_custom_props:
                family_location = Location.objects.get(pk=family_custom_props['location_id'])
                        
        qs_location = Location.objects.filter(type="V", validity_to__isnull=True)

        if custom_props and "current_village" in custom_props:
            village = custom_props.pop('current_village')
        elif custom_props and "current_village_id" in custom_props:
            village = qs_location.filter(current_village_id=custom_props.pop('current_village_id')).first()
        elif custom_props and "family" in custom_props:
            village = custom_props["family"].location
        elif family_location:
            village = family_location
        else:   
            village = create_test_village()

    
        family = get_from_custom_props(custom_props, 'family',  None)
        

        
        insuree = Insuree.objects.create(
            **{
                'last_name': get_from_custom_props(custom_props, 'last_name',"Test Last" ),
                'other_names': get_from_custom_props(custom_props, 'other_names', "First Second"),
                'family': family,
                'gender': get_from_custom_props(custom_props, 'gender', Gender.objects.get(code='M')),
                'dob': get_from_custom_props(custom_props, 'dob', '1972-08-09'),
                'chf_id': ref,
                'head': is_head,
                'card_issued': get_from_custom_props(custom_props, 'card_issued', True),
                'validity_from': get_from_custom_props(custom_props, 'validity_from',"2019-01-01"),
                'audit_user_id': get_from_custom_props(custom_props, 'audit_user_id',-1),
                'current_village': village,
                **custom_props
            }
        )
    if family is None:
        family = Family.objects.filter(head_insuree=insuree, *Family.filter_validity()).first()
    if with_family and family is None and insuree.family is None:
        if not family_custom_props:
            family_custom_props = {}
        if 'head_insuree' not in family_custom_props and 'head_insuree_id' not in family_custom_props:
            family_custom_props['head_insuree'] = insuree
        family_custom_props['location'] = village
        family = create_test_family(custom_props=family_custom_props)
        insuree.family = family
        insuree.save()
        
        # insuree2 =  create_test_insuree(
        #     with_family=False, 
        #     is_head=False, 
        #     custom_props={'family': family}, 
        #     family_custom_props=None
        # )

    
    family_custom_props = {}

    return insuree


def create_test_family(custom_props=None):
    if custom_props is None:
        custom_props = {}
    else:
        custom_props = {k: v for k, v in custom_props.items() if hasattr(Family, k)}
    family = None
    location = None
    if custom_props and "id" in custom_props:
        family = Family.objects.filter(id=custom_props['id']).first()
    if family is None and custom_props and "uuid" in custom_props:    
        family = Family.objects.filter(uuid=custom_props['uuid']).first()      
    if family is None:
        qs_location = Location.objects.filter(type="V")
        if custom_props and "location" in custom_props:
            location = custom_props.pop('location')
        elif custom_props and "location_id" in custom_props:
            location = qs_location.filter(location_id=custom_props.pop('location_id')).first()
        else:
            location = qs_location.filter(validity_to__isnull=True).first() 
            ## manage head
        head_insuree = custom_props.pop('head_insuree', Insuree.objects.filter(validity_to__isnull=True).first())    
            

        family = Family.objects.create(
            **{
                'validity_from': get_from_custom_props(custom_props, 'validity_from', "2019-01-01"),
                'audit_user_id': get_from_custom_props(custom_props, 'audit_user_id',-1),
                'head_insuree': head_insuree,
                'location': location,
                **custom_props
            }
        )

    return family



base64_blank_jpg = """
/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL
/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8
QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2Jyg
gkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLD
xMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ
3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eH
l6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+
iiigD//2Q==
"""
def get_from_custom_props( custom_props, elm, default):

    value= custom_props.pop(elm) if custom_props and elm in custom_props else default

    regex = re.compile("^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    regex_dt = re.compile("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$")
    if isinstance(value, str) and regex.match(value):
        value = datetime.strptime(value, "%Y-%m-%d")
    elif isinstance(value, str) and regex_dt.match(value):
        value = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    return value
    

def create_test_photo(insuree_id, officer_id, custom_props=None):
    if custom_props is None:
        custom_props = {}
    else:
        custom_props = {k: v for k, v in custom_props.items() if hasattr(InsureePhoto, k)}
    photo = InsureePhoto.objects.create(
        **{
            "insuree_id": insuree_id,
            "folder": InsureeConfig.insuree_photos_root_path,
            "officer_id": officer_id,
            "chf_id": "chfpic",
            "date": "2020-01-01",
            "validity_from": "2019-01-01",
            "audit_user_id": -1,
            "photo": base64_blank_jpg,
            **custom_props
        }
    )

    return photo


def create_test_gender():
    if Gender.objects.exists():
        return
    Gender.objects.bulk_create([
        Gender(code='F', gender='Female', alt_language=None, sort_order=2),
        Gender(code='M', gender='Male', alt_language=None, sort_order=1),
        Gender(code='O', gender='Other', alt_language=None, sort_order=3),
    ])


def create_test_profession():
    if Profession.objects.exists():
        return
    Profession.objects.bulk_create([
        Profession(id=1, profession='Housewife', sort_order=None, alt_language='Femme au foyer'),
        Profession(id=2, profession='Employee', sort_order=None, alt_language='Employé'),
        Profession(id=3, profession='Self Employee', sort_order=None, alt_language='Indépendant'),
        Profession(id=4, profession='Others', sort_order=None, alt_language='Autres'),
    ])


def create_test_education():
    if Education.objects.exists():
        return
    Education.objects.bulk_create([
        Education(id=1, education='Nursery', sort_order=None, alt_language='Garderie'),
        Education(id=2, education='Primary school', sort_order=None, alt_language='École primaire'),
        Education(id=3, education='Secondary school', sort_order=None, alt_language='École secondaire'),
        Education(id=4, education='University', sort_order=None, alt_language='Université'),
        Education(id=5, education='Postgraduate studies', sort_order=None, alt_language='Études supérieures'),
        Education(id=6, education='PHD', sort_order=None, alt_language='Doctorat'),
        Education(id=7, education='Other', sort_order=None, alt_language='Autre'),
    ])


def create_test_relation():
    if Relation.objects.exists():
        return
    Relation.objects.bulk_create([
        Relation(id=1, relation='Brother/Sister', sort_order=None, alt_language='Frère/soeur'),
        Relation(id=2, relation='Father/Mother', sort_order=None, alt_language='Père/Mère'),
        Relation(id=3, relation='Uncle/Aunt', sort_order=None, alt_language='Oncle/tante'),
        Relation(id=4, relation='Son/Daughter', sort_order=None, alt_language='Fils/fille'),
        Relation(id=5, relation='Grand parents', sort_order=None, alt_language='Grands/parents'),
        Relation(id=6, relation='Employee', sort_order=None, alt_language='Employé'),
        Relation(id=7, relation='Others', sort_order=None, alt_language='Autres'),
        Relation(id=8, relation='Spouse', sort_order=None, alt_language='Époux'),
    ])


def create_test_confirmation_type():
    if ConfirmationType.objects.exists():
        return
    ConfirmationType.objects.bulk_create([
        ConfirmationType(code='A', confirmationtype='Local council', sort_order=None, alt_language='Conseil local'),
        ConfirmationType(code='B', confirmationtype='Municipality', sort_order=None, alt_language='Municipalité'),
        ConfirmationType(code='C', confirmationtype='State', sort_order=None, alt_language='Etat'),
        ConfirmationType(code='D', confirmationtype='Other', sort_order=None, alt_language='Autre'),
    ])


def create_test_family_type():
    if FamilyType.objects.exists():
        return
    FamilyType.objects.bulk_create([
        FamilyType(code='N', type='Nuclear Family', sort_order=1, alt_language='Famille nucléaire'),
        FamilyType(code='E', type='Extended Family', sort_order=2, alt_language='Famille étendue'),
        FamilyType(code='S', type='Single Parent', sort_order=3, alt_language='Parent seul'),
        FamilyType(code='O', type='Other', sort_order=4, alt_language='Autre'),
        FamilyType(code='H', type='HouseHold', sort_order=5, alt_language='Famille'),
        FamilyType(code='G', type='Group', sort_order=6, alt_language='Groupe'),
    ])


def create_test_basic_identification_types():
    if IdentificationType.objects.exists():
        return
    IdentificationType.objects.bulk_create([
    IdentificationType(code='D', identification_type="Driver's Licence", alt_language=None, sort_order=1),
    IdentificationType(code='V', identification_type="Voter's ID", alt_language=None, sort_order=2),
    IdentificationType(code='N', identification_type="National ID", alt_language=None, sort_order=3),
    IdentificationType(code='P', identification_type="Passport", alt_language=None, sort_order=4),
    ])
