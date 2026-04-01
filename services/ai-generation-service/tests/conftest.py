import pytest


@pytest.fixture
def mock_openai_proposals_response():
    """Mock a successful OpenAI API response with 3 proposals."""
    return {
        "proposals": [
            {
                "copy_text": "\u00a1Descubre los mejores zapatos deportivos! Escr\u00edbenos por WhatsApp y recibe asesor\u00eda personalizada.",
                "script": "Escena 1: Mujer corriendo en el parque.\nEscena 2: Close-up de zapatos deportivos.\nEscena 3: WhatsApp CTA.",
                "image_prompt": "Professional photo of athletic shoes, vibrant colors, white background, commercial photography",
                "target_audience": {
                    "age_min": 25,
                    "age_max": 35,
                    "genders": ["female"],
                    "interests": ["fitness", "running", "fashion"],
                    "locations": ["CO"],
                },
                "cta_type": "whatsapp_chat",
                "whatsapp_number": None,
            },
            {
                "copy_text": "Zapatos que te llevan m\u00e1s lejos. Calidad y estilo en cada paso. \u00a1Ch\u00e1tea con nosotros!",
                "script": "Escena 1: Beneficios del producto.\nEscena 2: Comparativa de precios.\nEscena 3: Testimonios.\nEscena 4: CTA WhatsApp.",
                "image_prompt": "Stylish running shoes on a clean background, studio lighting, social media ad design",
                "target_audience": {
                    "age_min": 20,
                    "age_max": 40,
                    "genders": ["female", "male"],
                    "interests": ["sportswear", "fitness"],
                    "locations": ["CO"],
                },
                "cta_type": "whatsapp_chat",
                "whatsapp_number": None,
            },
            {
                "copy_text": "\u00a1\u00daltimas unidades! Aprovecha el 30% de descuento en zapatos deportivos. Escr\u00edbenos ya por WhatsApp.",
                "script": "Escena 1: Urgencia - stock limitado.\nEscena 2: Producto destacado.\nEscena 3: Descuento.\nEscena 4: Bot\u00f3n WhatsApp.",
                "image_prompt": "Sale banner for athletic shoes, urgency design, red accents, professional advertising photography",
                "target_audience": {
                    "age_min": 18,
                    "age_max": 45,
                    "genders": ["female", "male"],
                    "interests": ["deals", "online shopping", "sports"],
                    "locations": ["CO", "MX"],
                },
                "cta_type": "whatsapp_chat",
                "whatsapp_number": None,
            },
        ]
    }


@pytest.fixture
def mock_openai_mutate_response():
    """Mock a successful mutation response."""
    return {
        "mutated_proposal": {
            "copy_text": "Corre con estilo. Nuevos zapatos deportivos con tecnolog\u00eda avanzada. \u00a1Escr\u00edbenos por WhatsApp!",
            "script": "Escena 1: Atleta profesional.\nEscena 2: Tecnolog\u00eda del calzado.\nEscena 3: CTA WhatsApp.",
            "image_prompt": "High-tech athletic shoes, dynamic angle, professional advertising photography",
            "target_audience": {
                "age_min": 22,
                "age_max": 38,
                "genders": ["female"],
                "interests": ["fitness", "technology", "running"],
                "locations": ["CO"],
            },
            "cta_type": "whatsapp_chat",
            "whatsapp_number": None,
        },
        "mutations_applied": [
            "Changed copy angle from emotional to technology-focused",
            "Narrowed age range",
            "Added technology interest",
        ],
    }
