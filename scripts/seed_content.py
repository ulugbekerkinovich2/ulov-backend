import sys
import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.append(os.getcwd())

from app.config import settings
from app.modules.content.models import ContentPage
from app.modules.content.stories_models import Story
from app.modules.service_centers.models import ServiceCenter

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

def seed_content():
    # 1. Traffic Rules
    rules_data = [
        {
            "slug": "umumiy-qoidalar",
            "title": "Umumiy qoidalar",
            "body": {
                "icon": "FileText",
                "color": "from-blue-500 to-indigo-600",
                "description": "Yo'l harakati qoidalarining asosiy tushunchalari",
                "rules": [
                    {"id": "r1", "number": "1.1", "title": {"uz": "O'ng tomonlama harakat", "ru": "Правостороннее движение", "en": "Right-hand traffic"}, "body": {"uz": "Transport vositalarining o'ng tomonlama harakati belgilangan.", "ru": "Установлено правостороннее движение.", "en": "Right-hand traffic is established."}}
                ]
            }
        },
        {
            "slug": "haydovchilar-majburiyatlari",
            "title": "Haydovchilarning majburiyatlari",
            "body": {
                "icon": "UserCheck",
                "color": "from-emerald-500 to-teal-600",
                "description": "Haydovchilar bajarishi shart bo'lgan harakatlar",
                "rules": [
                    {"id": "r2", "number": "2.1", "title": {"uz": "Hujjatlarni olib yurish", "ru": "Наличие документов", "en": "Carrying documents"}, "body": {"uz": "Haydovchi yonida guvohnoma va texpasportni olib yurishi shart.", "ru": "Водитель обязан иметь при себе права и техпаспорт.", "en": "Driver must carry license and registration."}}
                ]
            }
        }
    ]
    for rd in rules_data:
        db.add(ContentPage(id=uuid.uuid4(), kind="traffic_rules", lang="uz", slug=rd["slug"], title=rd["title"], body=rd["body"]))

    # 2. Road Signs
    signs_data = [
        {
            "slug": "ogohlantiruvchi",
            "title": "Ogohlantiruvchi belgilar",
            "body": {
                "icon": "Triangle",
                "color": "from-red-500 to-orange-500",
                "description": "Xavfli yo'l qismlari haqida ogohlantirish",
                "signs": [
                    {"id": "s1", "code": "1.1", "name": {"uz": "Shlagbaumli temir yo'l o'tkazgichi", "ru": "Ж/д переезд со шлагбаумом", "en": "Railway crossing with barrier"}, "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/1.1_Uzbekistan_road_sign.svg/120px-1.1_Uzbekistan_road_sign.svg.png"}
                ]
            }
        }
    ]
    for sd in signs_data:
        db.add(ContentPage(id=uuid.uuid4(), kind="road_signs", lang="uz", slug=sd["slug"], title=sd["title"], body=sd["body"]))

    # 3. Fines
    fines_data = [
        {
            "slug": "speed",
            "title": "Tezlikni oshirish",
            "body": {
                "icon": "Gauge",
                "color": "from-orange-600 to-orange-400",
                "description": "Tezlikni buzish uchun jarimalar",
                "fines": [
                    {
                        "id": "speed-10-20",
                        "article": "128-1.1",
                        "title": {"uz": "Tezlikni 10–20 km/soat oshirish", "ru": "Превышение на 10-20", "en": "Speeding 10-20"},
                        "amount": {"uz": "187 500 so'm", "ru": "187 500 сум", "en": "187,500 UZS"},
                        "severity": "low",
                        "description": {"uz": "Tezlikni 10 dan 20 km gacha oshirish", "ru": "Превышение от 10 до 20 км/ч", "en": "Exceeding speed limit by 10-20 km/h"}
                    }
                ]
            }
        }
    ]
    for fd in fines_data:
        db.add(ContentPage(id=uuid.uuid4(), kind="fines", lang="uz", slug=fd["slug"], title=fd["title"], body=fd["body"]))

    # 4. Tips
    tips_data = [
        {
            "slug": "economy",
            "title": "Yoqilg'i tejash",
            "body": {
                "icon": "Zap",
                "color": "from-green-500 to-emerald-600",
                "description": "Yoqilg'ini qanday tejash bo'yicha maslahatlar",
                "tips": [
                    {"id": "t1", "title": {"uz": "Shinalar bosimi", "ru": "Давление в шинах", "en": "Tire pressure"}, "body": {"uz": "Shinalarda bosim past bo'lsa yoqilg'i sarfi oshadi.", "ru": "Низкое давление увеличивает расход.", "en": "Low pressure increases fuel consumption."}}
                ]
            }
        }
    ]
    for td in tips_data:
        db.add(ContentPage(id=uuid.uuid4(), kind="tips", lang="uz", slug=td["slug"], title=td["title"], body=td["body"]))

    # 5. Stories
    stories = [
        {
            "title": "Moy almashtirishda 20% chegirma!",
            "image_url": "https://images.unsplash.com/photo-1486006920555-c77dcf18193c?w=800&q=80",
            "content": "Faqat shu haftada Shell moylari uchun maxsus aksiya.",
            "discount_label": "-20%",
        }
    ]
    for s_data in stories:
        db.add(Story(id=uuid.uuid4(), title=s_data["title"], image_url=s_data["image_url"], content=s_data["content"], discount_label=s_data["discount_label"], is_active=True))

    db.commit()
    print("Seeding completed successfully.")

if __name__ == "__main__":
    seed_content()
