import sys
import os
import uuid
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.config import settings
from app.modules.content.models import ContentPage

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

def import_cms():
    print("Clearing existing content...")
    db.execute(text("DELETE FROM content_pages"))
    db.commit()

    # 1. TRAFFIC RULES
    traffic_rules_data = [
        {
            "id": "general",
            "icon": "BookOpen",
            "color": "from-primary to-primary-glow",
            "title": {"uz": "Umumiy qoidalar", "ru": "Общие положения", "en": "General provisions"},
            "description": {"uz": "Asosiy tushunchalar va haydovchining majburiyatlari", "ru": "Основные понятия и обязанности водителя", "en": "Basic concepts and driver duties"},
            "rules": [
                {
                    "id": "g1", "number": "2.1.1",
                    "title": {"uz": "Hujjatlar bilan ta'minlanish", "ru": "Наличие документов", "en": "Required documents"},
                    "body": {"uz": "Haydovchi o'zi bilan haydovchilik guvohnomasi, transport vositasini ro'yxatdan o'tkazganlik to'g'risidagi guvohnoma, OSAGO sug'urta polisi va texnik ko'rik talonini olib yurishi shart.", "ru": "Водитель обязан иметь при себе водительское удостоверение, свидетельство о регистрации ТС, страховой полис ОСАГО и талон техосмотра.", "en": "The driver must carry a driver's license, vehicle registration certificate, OSAGO insurance policy and technical inspection coupon."},
                    "fine": {"uz": "1 BHM (340 000 so'm)", "ru": "1 БРВ (340 000 сум)", "en": "1 BCV (~$28)"}
                },
                {
                    "id": "g2", "number": "2.1.2",
                    "title": {"uz": "Xavfsizlik kamarlari", "ru": "Ремни безопасности", "en": "Seat belts"},
                    "body": {"uz": "Haydovchi va barcha yo'lovchilar (orqa o'rindiqlardagilar ham) xavfsizlik kamarlarini taqib olishlari shart. 12 yoshgacha bolalar maxsus bolalar o'rindig'ida olib yurilishi kerak.", "ru": "Водитель и все пассажиры (включая задних) обязаны быть пристёгнуты ремнями безопасности. Дети до 12 лет — только в детском автокресле.", "en": "The driver and all passengers (including rear) must wear seat belts. Children under 12 must be in a child seat."},
                    "fine": {"uz": "0,5 BHM (170 000 so'm)", "ru": "0,5 БРВ (170 000 сум)", "en": "0.5 BCV (~$14)"}
                }
            ]
        },
        {
            "id": "speed",
            "icon": "Gauge",
            "color": "from-accent to-accent-glow",
            "title": {"uz": "Tezlik rejimi", "ru": "Скоростной режим", "en": "Speed limits"},
            "description": {"uz": "Aholi punktlari va trasselardagi tezlik chegaralari", "ru": "Ограничения скорости в населённых пунктах и на трассах", "en": "Speed limits in cities and highways"},
            "rules": [
                {
                    "id": "s1", "number": "10.2",
                    "title": {"uz": "Aholi punktlarida — 70 km/soat", "ru": "В населённых пунктах — 70 км/ч", "en": "In urban areas — 70 km/h"},
                    "body": {"uz": "Aholi punktlari hududida transport vositalarining harakatlanish tezligi 70 km/soatdan oshmasligi kerak. Hovli hududlarida — 20 km/soat.", "ru": "В населённых пунктах скорость не должна превышать 70 км/ч. Во дворах — 20 км/ч.", "en": "In urban areas, speed must not exceed 70 km/h. In residential yards — 20 km/h."}
                }
            ]
        }
    ]

    for cat in traffic_rules_data:
        for lang in ["uz", "ru", "en"]:
            # Localize rules for this lang
            localized_rules = []
            for r in cat["rules"]:
                localized_rules.append({
                    "id": r["id"],
                    "number": r["number"],
                    "title": {lang: r["title"][lang]},
                    "body": {lang: r["body"][lang]},
                    "fine": {lang: r["fine"][lang]} if "fine" in r else None
                })
            
            page = ContentPage(
                id=uuid.uuid4(),
                kind="traffic_rules",
                lang=lang,
                slug=cat["id"],
                title=cat["title"][lang],
                body={
                    "icon": cat["icon"],
                    "color": cat["color"],
                    "description": cat["description"][lang],
                    "rules": localized_rules
                }
            )
            db.add(page)

    # 2. ROAD SIGNS (Simplified categories)
    signs_cats = [
        {"id": "warning", "number": "1", "icon": "TriangleAlert", "color": "from-amber-500 to-orange-500", "title": {"uz": "Ogohlantiruvchi belgilar", "ru": "Предупреждающие знаки", "en": "Warning signs"}, "description": {"uz": "Yo'lda xavf borligini bildiradi", "ru": "Информируют об опасности на дороге", "en": "Warn about road hazards"}},
        {"id": "priority", "number": "2", "icon": "Octagon", "color": "from-orange-600 to-orange-400", "title": {"uz": "Ustunlik belgilari", "ru": "Знаки приоритета", "en": "Priority signs"}, "description": {"uz": "O'tish navbatini belgilaydi", "ru": "Устанавливают очерёдность проезда", "en": "Establish right of way"}}
    ]
    # Sample signs
    signs_data = [
        {"category": "warning", "number": "1.1", "file": "RU road sign 1.1.svg", "uz": "Temir yo'l o'tkazgichi", "ru": "Ж/д переезд", "en": "Railway crossing"},
        {"category": "priority", "number": "2.1", "file": "RU road sign 2.1.svg", "uz": "Asosiy yo'l", "ru": "Главная дорога", "en": "Main road"}
    ]

    for cat in signs_cats:
        for lang in ["uz", "ru", "en"]:
            localized_signs = []
            for s in [s for s in signs_data if s["category"] == cat["id"]]:
                localized_signs.append({
                    "number": s["number"],
                    "image": s["file"],
                    "name": {lang: s[lang]}
                })
            
            page = ContentPage(
                id=uuid.uuid4(),
                kind="road_signs",
                lang=lang,
                slug=cat["id"],
                title=cat["title"][lang],
                body={
                    "icon": cat["icon"],
                    "color": cat["color"],
                    "number": cat["number"],
                    "description": cat["description"][lang],
                    "signs": localized_signs
                }
            )
            db.add(page)

    # 3. FINES
    fines_cats = [
        {
            "id": "speed", "icon": "Gauge", "color": "from-orange-600 to-orange-400",
            "title": {"uz": "Tezlikni oshirish", "ru": "Превышение скорости", "en": "Speeding"},
            "description": {"uz": "Belgilangan tezlik chegarasini buzish", "ru": "Штрафы за превышение скорости", "en": "Speeding penalties"},
            "fines": [
                {
                    "id": "speed-10-20", "article": "128-1.1",
                    "title": {"uz": "Tezlikni 10–20 km/soat oshirish", "ru": "Превышение на 10-20", "en": "Speeding 10-20"},
                    "amount": {"uz": "187 500 so'm", "ru": "187 500 сум", "en": "187,500 UZS"},
                    "severity": "low",
                    "description": {"uz": "10 dan 20 km gacha oshirish", "ru": "От 10 до 20 км/ч", "en": "By 10-20 km/h"}
                }
            ]
        }
    ]
    for cat in fines_cats:
        for lang in ["uz", "ru", "en"]:
            localized_fines = []
            for f in cat["fines"]:
                localized_fines.append({
                    "id": f["id"], "article": f["article"],
                    "title": {lang: f["title"][lang]},
                    "amount": {lang: f["amount"][lang]},
                    "severity": f["severity"],
                    "description": {lang: f["description"][lang]}
                })
            page = ContentPage(
                id=uuid.uuid4(), kind="fines", lang=lang, slug=cat["id"], title=cat["title"][lang],
                body={
                    "icon": cat["icon"], "color": cat["color"],
                    "description": cat["description"][lang],
                    "fines": localized_fines
                }
            )
            db.add(page)

    # 4. TIPS
    tips_cats = [
        {
            "id": "winter", "icon": "Snowflake", "color": "from-sky-500 to-blue-500",
            "title": {"uz": "Qishki haydash", "ru": "Зимнее вождение", "en": "Winter driving"},
            "description": {"uz": "Sovuq mavsumda xavfsiz harakatlanish", "ru": "В холодный сезон", "en": "Cold season safety"},
            "tips": [
                {
                    "id": "winter-tires", "readTime": 3,
                    "title": {"uz": "Qishki shinalar", "ru": "Зимние шины", "en": "Winter tires"},
                    "body": {"uz": "Harorat 7 darajadan past tushganda almashtiring.", "ru": "Меняйте при < 7 градусов.", "en": "Switch below 7 degrees."}
                }
            ]
        }
    ]
    for cat in tips_cats:
        for lang in ["uz", "ru", "en"]:
            localized_tips = []
            for t in cat["tips"]:
                localized_tips.append({
                    "id": t["id"], "readTime": t["readTime"],
                    "title": {lang: t["title"][lang]},
                    "body": {lang: t["body"][lang]}
                })
            page = ContentPage(
                id=uuid.uuid4(), kind="tips", lang=lang, slug=cat["id"], title=cat["title"][lang],
                body={
                    "icon": cat["icon"], "color": cat["color"],
                    "description": cat["description"][lang],
                    "tips": localized_tips
                }
            )
            db.add(page)

    db.commit()
    print("CMS content imported successfully.")

if __name__ == "__main__":
    import_cms()
