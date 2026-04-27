"""Initial content seed (sample rows for each kind in uz/ru/en).

Ports a minimum subset of ``front-user/src/lib/{trafficRules,roadSigns,finesData,tipsData}``.
The full dataset will be migrated by a dedicated data-migration script that
reads the TypeScript sources. For the MVP we ship enough rows that the
customer app can render each screen.

Each entry is an ``(kind, lang, slug, title, body)`` tuple. ``body`` schema
is per-kind; the frontend treats ``body`` as opaque JSON.
"""

from __future__ import annotations

from typing import Any, List, Tuple

Row = Tuple[str, str, str, str, dict]

# ---------------------------------------------------------------------------
# Traffic rules
# ---------------------------------------------------------------------------
_TRAFFIC_RULES: List[Row] = [
    (
        "traffic_rules",
        "uz",
        "general",
        "Umumiy qoidalar",
        {
            "category": "general",
            "sections": [
                {
                    "title": "Haydovchi majburiyatlari",
                    "body": "Haydovchilik guvohnomasi, texnik pasport va OSAGO polisi doimo o'zingiz bilan bo'lsin.",
                },
                {
                    "title": "Xavfsizlik kamarlari",
                    "body": "Mashinadagi barcha yo'lovchilar xavfsizlik kamarini taqishi shart.",
                },
            ],
        },
    ),
    (
        "traffic_rules",
        "uz",
        "speed-limits",
        "Tezlik cheklovlari",
        {
            "category": "speed",
            "sections": [
                {"title": "Shahar ichida", "body": "60 km/soat — yo'l belgisi boshqacha ko'rsatmasa."},
                {"title": "Shahar tashqarisida", "body": "90 km/soat — asosiy yo'llar uchun."},
                {"title": "Avtomagistral", "body": "110 km/soat — maxsus yo'llar uchun."},
            ],
        },
    ),
]

# ---------------------------------------------------------------------------
# Road signs
# ---------------------------------------------------------------------------
_ROAD_SIGNS: List[Row] = [
    (
        "road_signs",
        "uz",
        "warning",
        "Ogohlantiruvchi belgilar",
        {
            "category": "warning",
            "signs": [
                {"code": "1.1", "name": "Temir yo'l o'tkazgichi", "image": "https://commons.wikimedia.org/wiki/File:Uzbekistan_road_sign_1.1.svg"},
                {"code": "1.11.1", "name": "Xavfli burilish", "image": "https://commons.wikimedia.org/wiki/File:Uzbekistan_road_sign_1.11.1.svg"},
            ],
        },
    ),
    (
        "road_signs",
        "uz",
        "priority",
        "Ustuvorlik belgilari",
        {
            "category": "priority",
            "signs": [
                {"code": "2.1", "name": "Asosiy yo'l", "image": ""},
                {"code": "2.4", "name": "Yo'l bering", "image": ""},
            ],
        },
    ),
]

# ---------------------------------------------------------------------------
# Fines
# ---------------------------------------------------------------------------
_FINES: List[Row] = [
    (
        "fines",
        "uz",
        "speed",
        "Tezlikni oshirish",
        {
            "category": "speed",
            "items": [
                {"description": "10–20 km/soat oshirish", "amount": "1 BHM", "notes": ""},
                {"description": "20–40 km/soat oshirish", "amount": "3 BHM", "notes": ""},
                {"description": "40+ km/soat oshirish", "amount": "5 BHM + guvohnoma 3 oy", "notes": ""},
            ],
        },
    ),
    (
        "fines",
        "uz",
        "drink",
        "Mast holda haydash",
        {
            "category": "drink",
            "items": [
                {"description": "Birinchi marta", "amount": "100 BHM + guvohnoma 3 yil", "notes": ""},
            ],
        },
    ),
]

# ---------------------------------------------------------------------------
# Tips
# ---------------------------------------------------------------------------
_TIPS: List[Row] = [
    (
        "tips",
        "uz",
        "winter",
        "Qishda haydash",
        {
            "category": "seasonal",
            "articles": [
                {
                    "title": "Qishki shinalar",
                    "body": "Havo harorati +7°C dan past tushsa, qishki shinalarga o'tish tavsiya etiladi.",
                },
                {
                    "title": "Antifriz darajasi",
                    "body": "Sovuq tushishidan oldin antifriz darajasini va tarkibini tekshiring.",
                },
            ],
        },
    ),
    (
        "tips",
        "uz",
        "fuel",
        "Yonilg'ini tejash",
        {
            "category": "economy",
            "articles": [
                {
                    "title": "Bir maromdagi tezlik",
                    "body": "80-90 km/soat tezlikda harakatlanish yonilg'i sarfini eng past ushlaydi.",
                },
            ],
        },
    ),
]


ALL_ROWS: List[Row] = _TRAFFIC_RULES + _ROAD_SIGNS + _FINES + _TIPS
