
import os
import uuid
from datetime import datetime, timedelta
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.modules.users.models import User
from app.modules.cars.models import Car
from app.modules.content.stories_models import Story
from app.modules.service_centers.models import ServiceCenter
from app.modules.services.models import Service, ServiceItem
from app.modules.fuel_stations.models import FuelStation

def seed_rich_data():
    db: Session = SessionLocal()
    try:
        # Find our main user
        user = db.query(User).filter(User.phone == "998901234567").first()
        if not user:
            print("User not found")
            return

        # 1. Add more cars for the user
        cars_to_add = [
            {
                "brand": "BYD",
                "model": "Song Plus",
                "year": 2023,
                "plate": "01 777 AAA",
                "plate_type": "standard",
                "color": "Oq",
                "vin": "BYD" + "".join([str(uuid.uuid4().int)[0] for _ in range(14)]),
                "mileage": 12500,
                "photo_url": "/Users/m3/.gemini/antigravity/brain/b188774a-1639-4c66-98b4-589f76c9b0c1/byd_song_plus_white_1777131454551.png"
            },
            {
                "brand": "BMW",
                "model": "M5",
                "year": 2022,
                "plate": "01 555 MMM",
                "plate_type": "standard",
                "color": "Qora",
                "vin": "WBS" + "".join([str(uuid.uuid4().int)[0] for _ in range(14)]),
                "mileage": 8200,
                "photo_url": "/Users/m3/.gemini/antigravity/brain/b188774a-1639-4c66-98b4-589f76c9b0c1/bmw_m5_black_1777131469256.png"
            }
        ]

        for c_data in cars_to_add:
            existing = db.query(Car).filter(Car.plate == c_data["plate"]).first()
            if not existing:
                new_car = Car(
                    owner_id=user.id,
                    **c_data
                )
                db.add(new_car)
                print(f"Added car: {c_data['brand']} {c_data['model']}")

        # 2. Add more stories
        stories_to_add = [
            {
                "title": "Yozgi shinalar mavsumi boshlandi!",
                "image_url": "/Users/m3/.gemini/antigravity/brain/b188774a-1639-4c66-98b4-589f76c9b0c1/summer_tires_promo_1777131483858.png",
                "content": "Sifatli yozgi shinalarni bizning servis markazlarimizda o'rnating va kafolatga ega bo'ling.",
                "discount_label": "KAFOLAT",
                "is_active": True
            },
            {
                "title": "Sug'urta uchun 20% chegirma",
                "image_url": "/Users/m3/.gemini/antigravity/brain/b188774a-1639-4c66-98b4-589f76c9b0c1/insurance_promo_banner_1777131502329.png",
                "content": "Yangi sug'urta polisini biz orqali rasmiylashtiring va 20% keshbekka ega bo'ling.",
                "discount_label": "20% CHEGIRMA",
                "is_active": True
            }
        ]

        for s_data in stories_to_add:
            existing = db.query(Story).filter(Story.title == s_data["title"]).first()
            if not existing:
                new_story = Story(**s_data)
                db.add(new_story)
                print(f"Added story: {s_data['title']}")

        # 3. Add Fuel Stations
        stations = [
            {
                "name": "Shell Tashkent",
                "brand": "Shell",
                "address": "Amir Temur ko'chasi, 10",
                "location": {"lat": 41.3111, "lng": 69.2797},
                "prices": {"ai92": 10500, "ai95": 12000, "diesel": 11500}
            },
            {
                "name": "Lukoil Navoi",
                "brand": "Lukoil",
                "address": "Navoiy shoh ko'chasi, 45",
                "location": {"lat": 41.3211, "lng": 69.2897},
                "prices": {"ai92": 10800, "ai95": 12500, "diesel": 11800}
            },
            {
                "name": "Mustang Petrol",
                "brand": "Mustang",
                "address": "Yunusobod 4-mavze",
                "location": {"lat": 41.3411, "lng": 69.3097},
                "prices": {"ai92": 10200, "ai95": 11800, "diesel": 11200}
            }
        ]

        for s_data in stations:
            existing = db.query(FuelStation).filter(FuelStation.name == s_data["name"]).first()
            if not existing:
                new_station = FuelStation(**s_data)
                db.add(new_station)
                print(f"Added fuel station: {s_data['name']}")

        db.commit()
        print("Successfully seeded rich data")

    except Exception as e:
        db.rollback()
        print(f"Error seeding data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_rich_data()
