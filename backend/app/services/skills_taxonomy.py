"""Skills Intelligence : taxonomie et normalisation des compétences (§8).

Charge ``data/skills_taxonomy.json`` et fournit :
- une normalisation tolerant (minuscules, accents supprimés, ponctuation) ;
- la résolution alias -> nom canonique (FR/EN) ;
- la détection de compétences dans un texte libre (correspondance exacte
  d'alias sur mots entiers, alias longs prioritaires).
"""
import json
import re
import unicodedata
from functools import lru_cache

from app import config


def normalize(text: str) -> str:
    """Minuscules + suppression des accents + ponctuation -> espaces."""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class SkillsTaxonomy:
    def __init__(self, entries: list[dict]):
        self.entries = entries
        self._aliases: dict[str, str] = {}      # alias normalisé -> canonique
        self._categories: dict[str, str] = {}   # canonique -> catégorie
        self._sorted_alias_patterns: list[tuple[str, re.Pattern[str], str]] = []
        for entry in entries:
            canonical = entry["name"]
            self._categories[canonical] = entry.get("category", "Autre")
            for alias in [canonical, *entry.get("aliases", [])]:
                norm = normalize(alias)
                if norm:
                    self._aliases[norm] = canonical
        self._sorted_alias_patterns = [
            (norm_alias, self._boundary_pattern(norm_alias), canonical)
            for norm_alias, canonical in sorted(
                self._aliases.items(), key=lambda kv: len(kv[0]), reverse=True
            )
        ]

    @staticmethod
    def _boundary_pattern(norm_alias: str) -> re.Pattern[str]:
        return re.compile(
            r"(?<![a-z0-9])" + re.escape(norm_alias) + r"(?![a-z0-9])"
        )

    def resolve(self, name: str) -> str | None:
        """Nom canonique si la chaîne correspond à une compétence connue."""
        return self._aliases.get(normalize(name))

    def canonical(self, name: str) -> str:
        return self.resolve(name) or name.strip()

    def category(self, name: str) -> str:
        canonical = self.resolve(name)
        if canonical:
            return self._categories[canonical]
        return self._categories.get(name.strip(), "Autre")

    def is_known(self, name: str) -> bool:
        return self.resolve(name) is not None

    def find_in_text(self, text: str) -> list[str]:
        """Compétences canoniques détectées, dans l'ordre de 1re apparition."""
        norm = normalize(text)
        found: list[tuple[int, str]] = []
        for _alias, pattern, canonical in self._sorted_alias_patterns:
            match = pattern.search(norm)
            if match and canonical not in (c for _, c in found):
                found.append((match.start(), canonical))
        return [c for _, c in sorted(found, key=lambda t: t[0])]

    def all_entries(self) -> list[dict]:
        return self.entries


@lru_cache(maxsize=1)
def load_taxonomy() -> SkillsTaxonomy:
    path = config.DATA_DIR / "skills_taxonomy.json"
    with open(path, encoding="utf-8") as f:
        return SkillsTaxonomy(json.load(f))
