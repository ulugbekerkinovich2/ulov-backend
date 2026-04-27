
import sys
import os
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

# Add app to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'app'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.db.session import SessionLocal
from app.modules.users.models import User
from app.modules.service_centers.models import ServiceCenter
from app.modules.mechanics.models import Mechanic
from app.modules.services.models import Service, ServiceItem, ServiceTransition
from app.modules.cars.models import Car

def seed_demo_data():
    db = SessionLocal()
    try:
        # 0. Ensure a default owner and center exist
        owner = db.query(User).filter(User.role == "owner").first()
        password_hash = "$argon2id$v=19$m=65536,t=3,p=4$qf9NcVmH+TMpwhgI9nRKUg$9fkH/0fEUuErwPR1Dyw2a53mF6Q8PnON7Olhxbczy+4" # password: '123456'
        if not owner:
            owner = User(
                id=uuid4(),
                phone="998901234567",
                password_hash=password_hash,
                full_name="Demo Owner",
                role="owner"
            )
            db.add(owner)
            db.flush()
        
        center = db.query(ServiceCenter).first()
        if not center:
            center = ServiceCenter(
                id=uuid4(),
                owner_user_id=owner.id,
                name="Ulov+ Auto Service",
                phone="998712003040",
                address="Toshkent sh., Yunusobod t.",
                services=["Moy almashtirish", "Xodovoy", "Elektrika"]
            )
            db.add(center)
            db.flush()
            
            # Link owner to center
            owner.center_id = center.id
            db.add(owner)
            db.flush()

        # Ensure some cars exist
        if not db.query(Car).first():
            car = Car(
                id=uuid4(),
                owner_id=owner.id,
                plate="01A777AA",
                plate_type="standard",
                brand="Chevrolet",
                model="Gentra",
                year=2022,
                color="Oq",
                vin="FFAKEVIN123456789",
                mileage=25000
            )
            db.add(car)
            db.flush()

        # 1. Find some centers
        centers = db.query(ServiceCenter).all()
        if not centers:
            print("No service centers found.")
            return

        # 2. Create mechanics for each center
        service_types = ["Moy almashtirish", "Xodovoy", "Elektrika", "Motor", "Kuzov", "Konditsioner"]
        
        mechanics = []
        for center in centers:
            # Create 3 mechanics per center
            for i in range(1, 4):
                login = f"mech_{center.id.hex[:4]}_{i}"
                existing = db.query(Mechanic).filter(Mechanic.login == login).first()
                if not existing:
                    mech = Mechanic(
                        id=uuid4(),
                        center_id=center.id,
                        full_name=f"Mechanic {i} ({center.name})",
                        login=login,
                        password_hash=password_hash,
                        service_types=random.sample(service_types, 3)
                    )
                    db.add(mech)
                    mechanics.append(mech)
        
        db.commit()
        print(f"Created {len(mechanics)} mechanics.")

        # 3. Create some cars if none exist
        cars = db.query(Car).all()

        # 4. Create historical services (last 30 days) + some ACTIVE ones
        now = datetime.now(tz=timezone.utc)
        statuses = ["completed", "completed", "completed", "cancelled", "completed", "waiting", "in_progress"]
        
        service_count = 0
        for _ in range(50): # Create 50 services
            car = random.choice(cars)
            center = random.choice(centers)
            center_mechanics = [m for m in mechanics if m.center_id == center.id]
            mechanic = random.choice(center_mechanics) if center_mechanics else None
            
            status = random.choice(statuses)
            # If active, set date to today. If completed, random last 30 days.
            if status in ["waiting", "in_progress"]:
                created_at = now - timedelta(hours=random.randint(0, 5))
            else:
                created_at = now - timedelta(days=random.randint(1, 30), hours=random.randint(0, 23))
            
            s = Service(
                id=uuid4(),
                car_id=car.id,
                center_id=center.id,
                mechanic_id=mechanic.id if mechanic else None,
                status=status,
                mileage_at_intake=car.mileage or 50000,
                created_at=created_at,
                notes="Demo service record"
            )
            
            if status == "completed":
                s.started_at = created_at + timedelta(minutes=15)
                s.completed_at = s.started_at + timedelta(minutes=random.randint(30, 180))
            elif status == "in_progress":
                s.started_at = created_at + timedelta(minutes=15)
            elif status == "cancelled":
                s.cancelled_at = created_at + timedelta(minutes=30)
                s.cancel_reason = "Mijoz rad etdi"
                
            db.add(s)
            
            # Add items
            item_count = random.randint(1, 3)
            for _ in range(item_count):
                stype = random.choice(service_types)
                s_price = random.randint(50000, 200000)
                p_price = random.randint(0, 500000)
                
                item = ServiceItem(
                    id=uuid4(),
                    service_id=s.id,
                    service_type=stype,
                    service_price=s_price,
                    parts_price=p_price,
                    created_at=created_at
                )
                db.add(item)
            
            service_count += 1
            
        db.commit()
        print(f"Created {service_count} historical service records.")

    finally:
        db.close()

if __name__ == "__main__":
    seed_demo_data()
