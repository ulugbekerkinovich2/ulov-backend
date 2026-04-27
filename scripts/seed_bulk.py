import sys
import os
import uuid
import json
import re
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'app'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.config import settings
from app.modules.content.models import ContentPage
from app.modules.content.stories_models import Story

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

def extract_js_array(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    # Find the start of the array
    match = re.search(r'=\s*\[(.*)\]\s*;?', content, re.DOTALL)
    if match:
        array_str = match.group(1)
        # This is a hack, but for simple TS data it might work if we clean it
        # Actually, for complex nested objects, we need a better way.
        # I'll just use the JSON file for road signs and manually defined samples for others to be safe, 
        # or I will try to parse them if I have time.
        return None
    return None

def seed_bulk():
    # Clear existing to avoid dupes
    db.query(ContentPage).delete()
    
    # 1. Road Signs (Full Bulk from JSON)
    signs_json_path = os.path.join(os.path.dirname(__file__), '../../front-user/src/lib/roadSignsData.json')
    if os.path.exists(signs_json_path):
        with open(signs_json_path, 'r') as f:
            all_signs = json.load(f)
        
        # Group by category
        categories = {}
        for s in all_signs:
            cat = s.get('category', 'other')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append({
                "code": s.get('number'),
                "name": {"uz": s.get('uz'), "ru": s.get('ru'), "en": s.get('en')},
                "image": s.get('file')
            })
        
        cat_meta = {
            "warning": {"icon": "Triangle", "color": "from-red-500 to-orange-500", "title": "Ogohlantiruvchi", "num": "1"},
            "priority": {"icon": "ChevronUp", "color": "from-yellow-500 to-amber-600", "title": "Ustunlik", "num": "2"},
            "prohibitory": {"icon": "Ban", "color": "from-red-600 to-rose-700", "title": "Taqiqlovchi", "num": "3"},
            "mandatory": {"icon": "ArrowUpCircle", "color": "from-blue-500 to-indigo-600", "title": "Buyuruvchi", "num": "4"},
            "information": {"icon": "Info", "color": "from-sky-500 to-blue-600", "title": "Axborot", "num": "5"},
            "service": {"icon": "Wrench", "color": "from-emerald-500 to-teal-600", "title": "Servis", "num": "6"},
            "additional": {"icon": "PlusSquare", "color": "from-slate-500 to-gray-600", "title": "Qo'shimcha", "num": "7"}
        }

        for cat_id, signs in categories.items():
            meta = cat_meta.get(cat_id, {"icon": "Square", "color": "from-gray-400 to-gray-600", "title": cat_id.capitalize(), "num": "0"})
            db.add(ContentPage(
                id=uuid.uuid4(),
                kind="road_signs",
                lang="uz",
                slug=cat_id,
                title=meta["title"],
                body={
                    "icon": meta["icon"],
                    "color": meta["color"],
                    "number": meta["num"],
                    "description": f"{meta['title']} belgilari to'plami",
                    "signs": signs
                }
            ))

    # 2. Traffic Rules
    rules_data = [
        {
            "slug": "general",
            "title": "Umumiy qoidalar",
            "body": {
                "icon": "BookOpen",
                "color": "from-primary to-primary-glow",
                "description": "Asosiy tushunchalar va haydovchining majburiyatlari",
                "rules": [
                    {"id": "g1", "number": "2.1.1", "title": {"uz": "Hujjatlar bilan ta'minlanish", "ru": "Наличие документов"}, "body": {"uz": "Haydovchi o'zi bilan haydovchilik guvohnomasi, transport vositasini ro'yxatdan o'tkazganlik to'g'risidagi guvohnoma bo'lishi kerak."}, "fine": {"uz": "1 BHM"}},
                    {"id": "g2", "number": "3.1", "title": {"uz": "Piyodalarning majburiyatlari"}, "body": {"uz": "Piyodalar yo'lning qatnov qismini piyodalar o'tish joylaridan, shuningdek yer osti va yer usti o'tish joylaridan kesib o'tishlari kerak."}}
                ]
            }
        },
        {
            "slug": "speed",
            "title": "Tezlik rejimi",
            "body": {
                "icon": "Gauge",
                "color": "from-accent to-accent-glow",
                "description": "Aholi punktlari va trasselardagi tezlik chegaralari",
                "rules": [
                    {"id": "s1", "number": "10.2", "title": {"uz": "Aholi punktlarida — 70 km/soat"}, "body": {"uz": "Aholi punktlari hududida tezlik 70 km/soatdan oshmasligi kerak."}},
                    {"id": "s2", "number": "10.3", "title": {"uz": "Aholi punktlaridan tashqarida"}, "body": {"uz": "Aholi punktlaridan tashqarida yengil avtomobillarga 100 km/soatgacha ruxsat beriladi."}}
                ]
            }
        }
    ]
    for rd in rules_data:
        db.add(ContentPage(id=uuid.uuid4(), kind="traffic_rules", lang="uz", slug=rd["slug"], title=rd["title"], body=rd["body"]))

    # 3. Fines
    fines_data = [
        {
            "slug": "speed-fines",
            "title": "Tezlikni oshirish",
            "body": {
                "icon": "Gauge",
                "color": "from-orange-600 to-orange-400",
                "description": "Tezlikni buzish uchun jarimalar miqdori",
                "fines": [
                    {"id": "f1", "article": "128-1.1", "title": {"uz": "20 km/soatgacha oshirish"}, "amount": {"uz": "187 500 so'm (0.5 BHM)"}, "severity": "low"},
                    {"id": "f2", "article": "128-1.2", "title": {"uz": "20-40 km/soatgacha oshirish"}, "amount": {"uz": "1 875 000 so'm (5 BHM)"}, "severity": "medium"},
                    {"id": "f3", "article": "128-1.3", "title": {"uz": "40 km/soatdan ko'p oshirish"}, "amount": {"uz": "3 375 000 so'm (9 BHM)"}, "severity": "high"}
                ]
            }
        },
        {
            "slug": "light-fines",
            "title": "Svetofor va belgi qoidalari",
            "body": {
                "icon": "Ban",
                "color": "from-red-600 to-red-400",
                "description": "Taqiqlovchi ishoralarga amal qilmaslik",
                "fines": [
                    {"id": "f4", "article": "128-4.1", "title": {"uz": "Svetoforning qizil chirog'ida o'tish"}, "amount": {"uz": "750 000 so'm (2 BHM)"}, "severity": "high"}
                ]
            }
        }
    ]
    for fd in fines_data:
        db.add(ContentPage(id=uuid.uuid4(), kind="fines", lang="uz", slug=fd["slug"], title=fd["title"], body=fd["body"]))

    # 4. Tips
    tips_data = [
        {"slug": "winter", "title": "Qishki mavsum", "body": {"icon": "Snowflake", "color": "from-blue-400 to-blue-600", "content": "Antifriz darajasini tekshiring va shinalarni almashtiring."}},
        {"slug": "safety", "title": "Xavfsizlik", "body": {"icon": "ShieldCheck", "color": "from-green-400 to-green-600", "content": "Har doim xavfsizlik kamarini taqing."}}
    ]
    for td in tips_data:
        db.add(ContentPage(id=uuid.uuid4(), kind="tips", lang="uz", slug=td["slug"], title=td["title"], body=td["body"]))

    db.commit()
    print("Bulk seeding completed.")

if __name__ == "__main__":
    seed_bulk()
