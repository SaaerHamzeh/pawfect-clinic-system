# -*- coding: utf-8 -*-
import os
import sys
import django
import datetime
from decimal import Decimal

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.clients.models import Client
from apps.patients.models import Animal

clients_data = [
    {
        'full_name': 'أحمد خالد الصالح',
        'phone': '0944112233',
        'address': 'دمشق - المزة فيلات غربية',
        'notes': 'عميل مميز، يلتزم بمواعيد التطعيم والفحص الدوري بدقة.',
        'pets': [
            {
                'name': 'لونا',
                'species': Animal.Species.CAT,
                'breed': 'شيرازي أصيل (Persian)',
                'gender': Animal.Gender.FEMALE,
                'birth_date': datetime.date(2024, 4, 10),
                'weight': Decimal('3.85'),
                'color': 'أبيض ثلجي',
                'identification': 'طوق جلدي أحمر، عيون زرقاء',
                'notes': 'هادئة ولطيفة، تحب التدليل وتخاف من الأصوات العالية.',
            },
            {
                'name': 'ماكس',
                'species': Animal.Species.DOG,
                'breed': 'جولدن ريتريفر (Golden Retriever)',
                'gender': Animal.Gender.MALE,
                'birth_date': datetime.date(2025, 2, 15),
                'weight': Decimal('22.40'),
                'color': 'ذهبي فاتح',
                'identification': 'شريحة إلكترونية تحت الجلد، طوق أزرق',
                'notes': 'نشيط وودود جداً مع الأطفال والحيوانات الأخرى.',
            },
        ]
    },
    {
        'full_name': 'ديما سامر الحلبي',
        'phone': '0933554422',
        'address': 'دمشق - أبو رمانة',
        'notes': 'تفضل التواصل عبر رسائل التذكير وتأكيد المواعيد قبل يوم.',
        'pets': [
            {
                'name': 'بيلا',
                'species': Animal.Species.CAT,
                'breed': 'بريطاني قصير الشعر (British Shorthair)',
                'gender': Animal.Gender.FEMALE,
                'birth_date': datetime.date(2024, 8, 20),
                'weight': Decimal('4.10'),
                'color': 'رمادي رصاصي (Blue)',
                'identification': 'عيون كهرمانية واسعة',
                'notes': 'صحة ممتازة، شهيتها جيدة للأطعمة الرطبة.',
            }
        ]
    },
    {
        'full_name': 'عمر مأمون الكردي',
        'phone': '0991887766',
        'address': 'ريف دمشق - جرمانا',
        'notes': 'مربي كلاب حراسة مدربة ومحترف في رعايتها.',
        'pets': [
            {
                'name': 'روكي',
                'species': Animal.Species.DOG,
                'breed': 'جيرمن شيبرد (German Shepherd)',
                'gender': Animal.Gender.MALE,
                'birth_date': datetime.date(2023, 11, 5),
                'weight': Decimal('31.50'),
                'color': 'أسود مع بني',
                'identification': 'أذنان منتصبتان، ندبة صغيرة أعلى الساق اليمنى',
                'notes': 'قوي ومطيع جداً، مدرب على الطاعة والحراسة.',
            }
        ]
    },
    {
        'full_name': 'نور عبد الرحمن النجار',
        'phone': '0955663322',
        'address': 'دمشق - المالكي',
        'notes': 'تهتم بالطيور المغردة وتتابع الفيتامينات الدورية بانتظام.',
        'pets': [
            {
                'name': 'تويتي',
                'species': Animal.Species.BIRD,
                'breed': 'كناري مغرد (Canary)',
                'gender': Animal.Gender.MALE,
                'birth_date': datetime.date(2025, 5, 12),
                'weight': Decimal('0.03'),
                'color': 'أصفر ليموني ناصع',
                'identification': 'حلقة معدنية برقم 42 في الساق اليسرى',
                'notes': 'تغريد متواصل، تم فحص الريش والمنقار وحالتهما ممتازة.',
            }
        ]
    },
    {
        'full_name': 'فراس عدنان المصري',
        'phone': '0988441199',
        'address': 'دمشق - التجارة',
        'notes': 'عميل جديد، قام بتبني أرنب هولندي مؤخراً.',
        'pets': [
            {
                'name': 'سيمو',
                'species': Animal.Species.OTHER,
                'breed': 'أرنب هولندي قزم (Netherland Dwarf)',
                'gender': Animal.Gender.FEMALE,
                'birth_date': datetime.date(2025, 9, 1),
                'weight': Decimal('1.25'),
                'color': 'أبيض مع بقع بنية حول العينين',
                'identification': 'آذان قصيرة منتصبة',
                'notes': 'فحص دوري للأسنان والجهاز الهضمي، يعتمد نظام غذائي غني بالقش والتبن (Hay).',
            }
        ]
    }
]

created_clients = 0
created_pets = 0

for cdata in clients_data:
    client, c_created = Client.objects.get_or_create(
        phone=cdata['phone'],
        defaults={
            'full_name': cdata['full_name'],
            'address': cdata['address'],
            'notes': cdata['notes'],
        }
    )
    if c_created:
        created_clients += 1
    
    for pdata in cdata['pets']:
        pet, p_created = Animal.objects.get_or_create(
            client=client,
            name=pdata['name'],
            defaults={
                'species': pdata['species'],
                'breed': pdata['breed'],
                'gender': pdata['gender'],
                'birth_date': pdata['birth_date'],
                'weight': pdata['weight'],
                'color': pdata['color'],
                'identification': pdata['identification'],
                'notes': pdata['notes'],
            }
        )
        if p_created:
            created_pets += 1
            print(f"تم إنشاء الحيوان: {pet.name} [{pet.animal_id}] ({pet.get_species_display()} - {pet.breed}) للمالك: {client.full_name}")

print(f"\nتمت العملية بنجاح: تم إنشاء {created_clients} عملاء و {created_pets} حيوانات.")
