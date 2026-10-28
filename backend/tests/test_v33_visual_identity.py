"""Audit de l'identité visuelle et de l'accessibilité (point 12)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

CSS_PATH = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "styles.css"
)
RADIUS_DECLARATION = re.compile(
    r"border(?:-(?:top|bottom)-(?:left|right))?-radius:\s*([^;]+);"
)


def _root_variables() -> dict[str, str]:
    css = CSS_PATH.read_text(encoding="utf-8")
    root = re.search(r":root\s*\{(.*?)\}", css, re.DOTALL)
    assert root, "Bloc :root introuvable dans styles.css"
    return {
        name: value.strip()
        for name, value in re.findall(
            r"--([\w-]+):\s*([^;]+);", root.group(1)
        )
    }


def _rgb(value: str) -> tuple[float, float, float]:
    value = value.strip()
    assert re.fullmatch(r"#[0-9a-fA-F]{6}", value), (
        f"Couleur hexadécimale attendue, reçu : {value}"
    )
    return tuple(
        int(value[index : index + 2], 16) / 255 for index in (1, 3, 5)
    )


def _luminance(value: str) -> float:
    channels = []
    for channel in _rgb(value):
        if channel <= 0.04045:
            channels.append(channel / 12.92)
        else:
            channels.append(((channel + 0.055) / 1.055) ** 2.4)
    return (
        0.2126 * channels[0]
        + 0.7152 * channels[1]
        + 0.0722 * channels[2]
    )


def _contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (_luminance(foreground), _luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_radius_scale_is_unique_and_complete():
    variables = _root_variables()

    assert variables["radius-xs"] == "4px"
    assert variables["radius-sm"] == "6px"
    assert variables["radius"] == "8px"
    assert variables["radius-lg"] == "10px"
    assert variables["radius-xl"] == "12px"
    assert variables["radius-pill"] == "999px"


def test_no_hardcoded_pixel_radius_remains():
    css = CSS_PATH.read_text(encoding="utf-8")
    offenders = []
    for match in RADIUS_DECLARATION.finditer(css):
        value = match.group(1).strip()
        if value in {"0", "inherit"}:
            continue
        if "%" in value:
            continue
        if "var(" in value:
            continue
        offenders.append(value)

    assert not offenders, (
        "Rayons codés en dur hors échelle : " + ", ".join(offenders)
    )


def test_badges_chips_and_sections_use_institutional_shapes():
    css = CSS_PATH.read_text(encoding="utf-8")

    assert re.search(
        r"\.badge,[\s\S]*?\{\s*border-radius:\s*var\(--radius-xs\);\s*\}",
        css,
    ), "Les badges doivent utiliser le rayon xs."
    assert re.search(
        r"\.chip,[\s\S]*?\{\s*border-radius:\s*var\(--radius-sm\);\s*\}",
        css,
    ), "Les chips doivent utiliser le rayon sm."
    assert ".section-head {" in css
    assert "border-bottom: 1px solid var(--border);" in css


def test_key_text_combinations_meet_wcag_aa():
    variables = _root_variables()
    white = "#ffffff"

    pairs = [
        ("texte principal sur surface", variables["text"], variables["panel"], 7.0),
        ("texte secondaire sur surface", variables["muted"], variables["panel"], 4.5),
        ("texte secondaire sur fond", variables["muted"], variables["bg"], 4.5),
        ("lien vert sur surface", variables["green"], variables["panel"], 4.5),
        ("accent sur surface", variables["accent"], variables["panel"], 4.5),
        ("blanc sur vert", white, variables["green"], 4.5),
        ("blanc sur accent", white, variables["accent"], 4.5),
        ("blanc sur ardoise", white, variables["slate"], 4.5),
        ("blanc sur danger", white, variables["danger"], 4.5),
        ("vert profond sur vert clair", variables["green-ink"], variables["green-soft"], 4.5),
        ("avertissement sur accent clair", variables["warn"], variables["accent-soft"], 4.5),
    ]

    failures = []
    for label, foreground, background, minimum in pairs:
        ratio = _contrast(foreground, background)
        if ratio < minimum:
            failures.append(
                f"{label} : {ratio:.2f}:1, minimum {minimum}:1"
            )

    assert not failures, "Contrastes insuffisants : " + " ; ".join(failures)
