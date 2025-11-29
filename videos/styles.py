"""Central definitions for music video styles and prompts."""
from typing import Dict, List, Tuple

STYLE_DEFINITIONS: List[Dict[str, str]] = [
    {
        "key": "lyric_simple",
        "label": "Simple Lyric Video",
        "default_prompt": "Generate a video where the lyrics of the song appear centered on screen over a clean background. Use smooth fade transitions for each line. Music must be synced to text duration.",
    },
    {
        "key": "karaoke",
        "label": "Karaoke Style",
        "default_prompt": "Create a karaoke-style video where lyrics appear word-by-word and highlight in yellow while singing. Add a bouncing ball effect if possible.",
    },
    {
        "key": "motion_graphic",
        "label": "Abstract Motion Graphics",
        "default_prompt": "Generate a music video with animated abstract shapes reacting to the beat. Use pulsing neon colors that match the frequency peaks of the music.",
    },
    {
        "key": "dark_emotional",
        "label": "Dark Emotional",
        "default_prompt": "Make a music video with slow camera motion, dark tones, deep shadows, rain ambiance, glitch text transitions and emotional mood.",
    },
    {
        "key": "romantic",
        "label": "Romantic",
        "default_prompt": "Generate a romantic lyric video with soft pink tones, bokeh lights, smooth slow zooms and handwritten-style typography animations.",
    },
    {
        "key": "rap_hiphop",
        "label": "Rap / Hip-Hop",
        "default_prompt": "Create a fast-cut hip-hop music video with graffiti-style motion graphics, bass-reactive typography, camera shake and high BPM sync.",
    },
    {
        "key": "cyberpunk",
        "label": "Cyberpunk / Neon City",
        "default_prompt": "Build a music video with neon city visuals, rainy streets, hologram-like lyrics, purple-blue color scheme and techno beat pulsing lights.",
    },
    {
        "key": "ai_surreal",
        "label": "AI Surreal / Abstract",
        "default_prompt": "Generate a music video using AI surreal visuals: abstract, dream-like, hallucination-style motion synced with the song.",
    },
    {
        "key": "cinematic",
        "label": "Epic Cinematic",
        "default_prompt": "Create a cinematic music video with dramatic lighting, slow motion shots, deep bass hits, gold typography and light flare effects.",
    },
    {
        "key": "landscape",
        "label": "Nature Landscape",
        "default_prompt": "Use landscape footage (mountains, oceans, forests) with soft dissolves and poetic typography. Calm and atmospheric background.",
    },
    {
        "key": "party_edm",
        "label": "EDM / Party",
        "default_prompt": "Generate an energetic EDM party video with multi-color strobe lights, strong beat flashes, rotating text, zoom transitions and glitch effects.",
    },
    {
        "key": "ai_avatar",
        "label": "AI Avatar Performance",
        "default_prompt": "Generate a video with an AI avatar performing the song, approximate lip-sync, dynamic camera movements and soft bloom highlights.",
    },
]


def get_all_styles() -> List[Dict[str, str]]:
    return STYLE_DEFINITIONS


def get_style_choices() -> List[Tuple[str, str]]:
    return [(style["key"], style["label"]) for style in STYLE_DEFINITIONS]


def get_style_by_key(key: str) -> Dict[str, str]:
    for style in STYLE_DEFINITIONS:
        if style["key"] == key:
            return style
    return {}


def get_default_prompt_for_style(key: str) -> str:
    style = get_style_by_key(key)
    return style.get("default_prompt", "")


def get_style_label(key: str) -> str:
    style = get_style_by_key(key)
    return style.get("label", key)
