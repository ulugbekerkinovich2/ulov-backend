"""ModelView definitions for the sqladmin panel.

Every model that earns a place in the admin UI is registered here. We pick
"useful for support" columns for the listing page and let the detail view
expose everything else — sqladmin gives us search, filters, pagination and
edit forms more or less for free.

Sensitive columns (password_hash, refresh tokens) are intentionally not
exposed for editing. Reading them is fine for support; rewriting an
argon2 hash by hand is not.
"""

from __future__ import annotations

from sqladmin import ModelView

from app.modules.audit.models import AuditLog
from app.modules.billing.models import Payment, SubscriptionPlan
from app.modules.cars.models import Car, MileageReading
from app.modules.content.models import ContentPage
from app.modules.content.stories_models import Story
from app.modules.fuel_stations.models import FuelStation
from app.modules.insurance.models import (
    InsuranceCompany,
    InsurancePolicy,
    InsuranceTariff,
)
from app.modules.mechanics.models import Mechanic
from app.modules.notifications.models import Device, Notification
from app.modules.reviews.models import Review
from app.modules.service_centers.models import ServiceCenter
from app.modules.services.models import (
    ConditionImage,
    Service,
    ServiceItem,
    ServiceTransition,
)
from app.modules.sos.models import SosProvider, SosRequest
from app.modules.trips.models import Trip, TripPoint
from app.modules.users.models import User


# ---------------------------------------------------------------------------
# Identity / accounts
# ---------------------------------------------------------------------------
class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"
    category = "Accounts"

    column_list = [
        User.id,
        User.phone,
        User.full_name,
        User.role,
        User.center_id,
        User.is_active,
        User.created_at,
    ]
    column_searchable_list = [User.phone, User.full_name, User.email]
    column_sortable_list = [User.created_at, User.phone, User.role]
    form_excluded_columns = ["password_hash"]


class MechanicAdmin(ModelView, model=Mechanic):
    name = "Mechanic"
    name_plural = "Mechanics"
    icon = "fa-solid fa-screwdriver-wrench"
    category = "Accounts"
    column_list = [
        Mechanic.id,
        Mechanic.center_id,
        Mechanic.full_name,
        Mechanic.login,
        Mechanic.deleted_at,
        Mechanic.created_at,
    ]
    column_searchable_list = [Mechanic.full_name, Mechanic.login]
    form_excluded_columns = ["password_hash"]


# ---------------------------------------------------------------------------
# Centres / cars
# ---------------------------------------------------------------------------
class ServiceCenterAdmin(ModelView, model=ServiceCenter):
    name = "Service centre"
    name_plural = "Service centres"
    icon = "fa-solid fa-warehouse"
    category = "Centres"
    column_list = [
        ServiceCenter.id,
        ServiceCenter.name,
        ServiceCenter.phone,
        ServiceCenter.address,
        ServiceCenter.owner_user_id,
        ServiceCenter.created_at,
    ]
    column_searchable_list = [
        ServiceCenter.name,
        ServiceCenter.phone,
        ServiceCenter.address,
    ]


class CarAdmin(ModelView, model=Car):
    name = "Car"
    name_plural = "Cars"
    icon = "fa-solid fa-car"
    category = "Centres"
    column_list = [
        Car.id,
        Car.plate,
        Car.brand,
        Car.model,
        Car.year,
        Car.vin,
        Car.tech_passport,
        Car.owner_id,
        Car.created_at,
    ]
    column_searchable_list = [Car.plate, Car.vin, Car.tech_passport]
    column_sortable_list = [Car.created_at, Car.year, Car.brand]


class MileageReadingAdmin(ModelView, model=MileageReading):
    name = "Mileage reading"
    name_plural = "Mileage readings"
    icon = "fa-solid fa-gauge-high"
    category = "Centres"
    column_list = [
        MileageReading.id,
        MileageReading.car_id,
        MileageReading.value,
        MileageReading.source,
        MileageReading.recorded_at,
    ]
    column_sortable_list = [MileageReading.recorded_at]


# ---------------------------------------------------------------------------
# Services pipeline
# ---------------------------------------------------------------------------
class ServiceAdmin(ModelView, model=Service):
    name = "Service"
    name_plural = "Services"
    icon = "fa-solid fa-screwdriver-wrench"
    category = "Services"
    column_list = [
        Service.id,
        Service.car_id,
        Service.center_id,
        Service.mechanic_id,
        Service.status,
        Service.mileage_at_intake,
        Service.created_at,
        Service.completed_at,
    ]
    column_sortable_list = [Service.created_at, Service.completed_at, Service.status]


class ServiceItemAdmin(ModelView, model=ServiceItem):
    name = "Service item"
    name_plural = "Service items"
    icon = "fa-solid fa-list-check"
    category = "Services"
    column_list = [
        ServiceItem.id,
        ServiceItem.service_id,
        ServiceItem.service_type,
        ServiceItem.service_price,
        ServiceItem.parts_price,
    ]
    column_searchable_list = [ServiceItem.service_type]


class ServiceTransitionAdmin(ModelView, model=ServiceTransition):
    name = "Service transition"
    name_plural = "Service transitions"
    icon = "fa-solid fa-clock-rotate-left"
    category = "Services"
    can_create = False
    can_edit = False
    can_delete = False
    column_list = [
        ServiceTransition.id,
        ServiceTransition.service_id,
        ServiceTransition.from_status,
        ServiceTransition.to_status,
        ServiceTransition.by_user_id,
        ServiceTransition.at,
    ]


class ConditionImageAdmin(ModelView, model=ConditionImage):
    name = "Condition photo"
    name_plural = "Condition photos"
    icon = "fa-solid fa-camera"
    category = "Services"
    column_list = [
        ConditionImage.id,
        ConditionImage.service_id,
        ConditionImage.stage,
        ConditionImage.url,
        ConditionImage.at,
    ]


class ReviewAdmin(ModelView, model=Review):
    name = "Review"
    name_plural = "Reviews"
    icon = "fa-solid fa-star"
    category = "Services"
    column_list = [
        Review.id,
        Review.user_id,
        Review.center_id,
        Review.rating,
        Review.text,
    ]


# ---------------------------------------------------------------------------
# Customer-side
# ---------------------------------------------------------------------------
class TripAdmin(ModelView, model=Trip):
    name = "Trip"
    name_plural = "Trips"
    icon = "fa-solid fa-route"
    category = "Customer"
    column_list = [
        Trip.id,
        Trip.car_id,
        Trip.user_id,
        Trip.distance_km,
        Trip.duration_s,
        Trip.started_at,
        Trip.finished_at,
    ]
    column_sortable_list = [Trip.started_at, Trip.distance_km]


class TripPointAdmin(ModelView, model=TripPoint):
    name = "Trip point"
    name_plural = "Trip points"
    icon = "fa-solid fa-location-dot"
    category = "Customer"
    can_create = False
    can_edit = False
    column_list = [
        TripPoint.id,
        TripPoint.trip_id,
        TripPoint.lat,
        TripPoint.lng,
        TripPoint.speed,
        TripPoint.ts,
    ]


class NotificationAdmin(ModelView, model=Notification):
    name = "Notification"
    name_plural = "Notifications"
    icon = "fa-solid fa-bell"
    category = "Customer"
    column_list = [
        Notification.id,
        Notification.user_id,
        Notification.kind,
        Notification.title,
        Notification.read_at,
        Notification.created_at,
    ]
    column_searchable_list = [Notification.title, Notification.kind]


class DeviceAdmin(ModelView, model=Device):
    name = "Device"
    name_plural = "Devices"
    icon = "fa-solid fa-mobile-screen"
    category = "Customer"
    column_list = [
        Device.id,
        Device.user_id,
        Device.platform,
        Device.token,
        Device.created_at,
    ]


# ---------------------------------------------------------------------------
# Reference / content
# ---------------------------------------------------------------------------
class StoryAdmin(ModelView, model=Story):
    name = "Story"
    name_plural = "Stories"
    icon = "fa-solid fa-images"
    category = "Content"
    column_list = [
        Story.id,
        Story.title,
        Story.center_id,
        Story.is_active,
        Story.valid_until,
        Story.created_at,
    ]
    column_searchable_list = [Story.title]


class ContentPageAdmin(ModelView, model=ContentPage):
    name = "Content page"
    name_plural = "Content pages"
    icon = "fa-solid fa-file-lines"
    category = "Content"
    column_list = [
        ContentPage.id,
        ContentPage.kind,
        ContentPage.lang,
        ContentPage.slug,
        ContentPage.title,
        ContentPage.updated_at,
    ]
    column_searchable_list = [ContentPage.slug, ContentPage.title, ContentPage.kind]


class FuelStationAdmin(ModelView, model=FuelStation):
    name = "Fuel station"
    name_plural = "Fuel stations"
    icon = "fa-solid fa-gas-pump"
    category = "Content"
    column_list = [
        FuelStation.id,
        FuelStation.name,
        FuelStation.brand,
        FuelStation.address,
    ]
    column_searchable_list = [FuelStation.name, FuelStation.brand, FuelStation.address]


class SosProviderAdmin(ModelView, model=SosProvider):
    name = "SOS provider"
    name_plural = "SOS providers"
    icon = "fa-solid fa-truck-medical"
    category = "Content"
    column_list = [
        SosProvider.id,
        SosProvider.category,
        SosProvider.name,
        SosProvider.phone,
        SosProvider.city,
    ]


class SosRequestAdmin(ModelView, model=SosRequest):
    name = "SOS request"
    name_plural = "SOS requests"
    icon = "fa-solid fa-triangle-exclamation"
    category = "Content"
    can_create = False
    can_edit = False
    column_list = [
        SosRequest.id,
        SosRequest.user_id,
        SosRequest.provider_id,
        SosRequest.status,
        SosRequest.lat,
        SosRequest.lng,
        SosRequest.created_at,
    ]


# ---------------------------------------------------------------------------
# Insurance
# ---------------------------------------------------------------------------
class InsuranceCompanyAdmin(ModelView, model=InsuranceCompany):
    name = "Insurance company"
    name_plural = "Insurance companies"
    icon = "fa-solid fa-shield"
    category = "Insurance"
    column_list = [
        InsuranceCompany.id,
        InsuranceCompany.name,
        InsuranceCompany.base_price,
        InsuranceCompany.rating,
        InsuranceCompany.active,
    ]


class InsuranceTariffAdmin(ModelView, model=InsuranceTariff):
    name = "Insurance tariff"
    name_plural = "Insurance tariffs"
    icon = "fa-solid fa-tags"
    category = "Insurance"
    column_list = [
        InsuranceTariff.id,
        InsuranceTariff.code,
        InsuranceTariff.name,
        InsuranceTariff.base_price,
        InsuranceTariff.active,
    ]


class InsurancePolicyAdmin(ModelView, model=InsurancePolicy):
    name = "Insurance policy"
    name_plural = "Insurance policies"
    icon = "fa-solid fa-file-shield"
    category = "Insurance"
    column_list = [
        InsurancePolicy.id,
        InsurancePolicy.car_id,
        InsurancePolicy.company_id,
        InsurancePolicy.payment_status,
        InsurancePolicy.valid_from,
        InsurancePolicy.valid_to,
        InsurancePolicy.price,
    ]


# ---------------------------------------------------------------------------
# Billing / audit
# ---------------------------------------------------------------------------
class SubscriptionPlanAdmin(ModelView, model=SubscriptionPlan):
    name = "Subscription plan"
    name_plural = "Subscription plans"
    icon = "fa-solid fa-tags"
    category = "Billing"
    column_list = [
        SubscriptionPlan.id,
        SubscriptionPlan.code,
        SubscriptionPlan.name,
        SubscriptionPlan.monthly_price,
        SubscriptionPlan.duration_days,
        SubscriptionPlan.active,
    ]


class PaymentAdmin(ModelView, model=Payment):
    name = "Payment"
    name_plural = "Payments"
    icon = "fa-solid fa-money-bill"
    category = "Billing"
    can_create = False
    column_list = [
        Payment.id,
        Payment.user_id,
        Payment.kind,
        Payment.plan_id,
        Payment.provider,
        Payment.amount,
        Payment.status,
        Payment.created_at,
    ]


class AuditLogAdmin(ModelView, model=AuditLog):
    name = "Audit log"
    name_plural = "Audit logs"
    icon = "fa-solid fa-shield-halved"
    category = "Billing"
    can_create = False
    can_edit = False
    can_delete = False
    column_list = [
        AuditLog.id,
        AuditLog.actor_user_id,
        AuditLog.actor_role,
        AuditLog.entity_type,
        AuditLog.entity_id,
        AuditLog.action,
        AuditLog.at,
    ]
    column_searchable_list = [AuditLog.entity_type, AuditLog.action]


# Export tuple consumed by setup.mount_admin().
ADMIN_VIEWS = (
    UserAdmin,
    MechanicAdmin,
    ServiceCenterAdmin,
    CarAdmin,
    MileageReadingAdmin,
    ServiceAdmin,
    ServiceItemAdmin,
    ServiceTransitionAdmin,
    ConditionImageAdmin,
    ReviewAdmin,
    TripAdmin,
    TripPointAdmin,
    NotificationAdmin,
    DeviceAdmin,
    StoryAdmin,
    ContentPageAdmin,
    FuelStationAdmin,
    SosProviderAdmin,
    SosRequestAdmin,
    InsuranceCompanyAdmin,
    InsuranceTariffAdmin,
    InsurancePolicyAdmin,
    SubscriptionPlanAdmin,
    PaymentAdmin,
    AuditLogAdmin,
)
