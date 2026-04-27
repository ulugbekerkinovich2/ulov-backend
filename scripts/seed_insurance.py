
import sys
import os
import random
from uuid import uuid4

# Add app to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'app'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.config import settings
from app.modules.insurance.models import InsuranceCompany, InsuranceTariff
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def seed_insurance_data():
    db = SessionLocal()
    try:
        companies_data = [
            {
                "name": "Uzbekinvest",
                "rating": 4.8,
                "reviews_count": 1240,
                "base_price": 100000,
                "perks": ["Tezkor to'lov", "24/7 yordam", "Evakuatsiya bepul"]
            },
            {
                "name": "Gross Insurance",
                "rating": 4.7,
                "reviews_count": 850,
                "base_price": 95000,
                "perks": ["Online ariza", "Keshbek 5%", "Yengil shartlar"]
            },
            {
                "name": "Alfa Invest",
                "rating": 4.5,
                "reviews_count": 620,
                "base_price": 105000,
                "perks": ["Yirik qoplama", "VIP xizmat"]
            },
            {
                "name": "Kapital Sug'urta",
                "rating": 4.6,
                "reviews_count": 430,
                "base_price": 98000,
                "perks": ["Barcha hududlarda", "Tezkor rasmiylashtirish"]
            }
        ]

        for data in companies_data:
            existing = db.query(InsuranceCompany).filter(InsuranceCompany.name == data["name"]).first()
            if not existing:
                company = InsuranceCompany(
                    id=uuid4(),
                    name=data["name"],
                    rating=int(data["rating"] * 10), # scale to biging if needed or just use as is
                    reviews_count=data["reviews_count"],
                    base_price=data["base_price"],
                    perks=data["perks"]
                )
                db.add(company)
        
        # Also seed a default tariff
        existing_tariff = db.query(InsuranceTariff).filter(InsuranceTariff.code == "osago_yillik").first()
        if not existing_tariff:
            tariff = InsuranceTariff(
                id=uuid4(),
                code="osago_yillik",
                name="Yillik OSAGO",
                base_price=100000,
                coefficients={
                    "brand": {"Chevrolet": 1.0, "BMW": 1.5},
                    "year_band": {"2020+": 1.0, "2015-2019": 1.1, "pre-2010": 1.3}
                },
                active=True
            )
            db.add(tariff)

        db.commit()
        print("Insurance data seeded.")

    finally:
        db.close()

if __name__ == "__main__":
    seed_insurance_data()
