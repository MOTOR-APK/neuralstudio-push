"""Estilos visuais prontos.

Cada estilo é um sufixo em inglês adicionado ao prompt — o SD-Turbo
foi treinado em inglês, então isso melhora bastante o resultado.
"""

ESTILOS = {
    "Sem estilo": "",
    "Fotorrealista": (
        ", photorealistic, highly detailed, natural lighting, "
        "sharp focus, 8k, professional photography"
    ),
    "Cinematográfico": (
        ", cinematic lighting, dramatic shadows, film still, "
        "anamorphic lens, movie scene, color graded"
    ),
    "Anime": (
        ", anime style, vibrant colors, clean line art, "
        "detailed illustration, studio quality"
    ),
    "Cartoon": (
        ", cartoon style, bold outlines, flat colors, "
        "playful, expressive, clean background"
    ),
    "Pintura a óleo": (
        ", oil painting, textured brush strokes, classical art, "
        "rich colors, canvas texture"
    ),
    "Aquarela": (
        ", watercolor painting, soft washes, delicate details, "
        "paper texture, artistic"
    ),
    "Cyberpunk": (
        ", cyberpunk, neon lights, futuristic city, rain, "
        "high contrast, glowing reflections"
    ),
    "3D Render": (
        ", 3d render, octane render, soft studio lighting, "
        "high detail, polished, subsurface scattering"
    ),
    "Minimalista": (
        ", minimalist, clean background, simple shapes, "
        "negative space, elegant, flat design"
    ),
    "Fantasia": (
        ", fantasy art, magical atmosphere, ethereal light, "
        "epic composition, intricate details"
    ),
    "Vintage": (
        ", vintage photography, film grain, faded colors, "
        "retro aesthetic, 1970s"
    ),
}

PROPORCOES = {
    "1:1": (512, 512),
    "16:9": (640, 384),
    "9:16": (384, 640),
    "4:3": (512, 384),
}

PROMPTS_ALEATORIOS = [
    "a majestic mountain landscape at sunrise, misty valley, dramatic clouds",
    "a cozy coffee shop interior, warm light, plants, rain outside the window",
    "a futuristic city skyline at night, neon signs, flying cars, reflections on wet streets",
    "a cute robot reading a book in a library, soft lighting, detailed",
    "an ancient temple in the jungle, overgrown vines, god rays, mysterious",
    "a portrait of an old fisherman, weathered face, detailed eyes, natural light",
    "a bowl of ramen, steam rising, top view, food photography, vibrant colors",
    "a dragon flying over a medieval castle, epic scale, sunset",
    "a space station orbiting a colorful planet, stars, sci-fi, detailed",
    "a cat wearing a tiny astronaut helmet, studio photo, adorable",
]
