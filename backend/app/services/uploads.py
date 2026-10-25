"""Résolution des chemins de fichiers déposés (photos, pièces d'identité).

Deux formats cohabitent en base :
- ancien : chemin relatif au backend (« uploads/photos/user_1.jpg »),
  inscrit quand le dossier des dépôts vivait sous backend/ ;
- bac à sable : relatif à ``UPLOAD_DIR`` (« photos/user_1.jpg »), quand
  l'environnement (tests, smoke) isole les dépôts de la vraie base.

Une seule règle : les tests et le smoke fixent ``UPLOAD_DIR`` vers un
dossier jetable, jamais vers les fichiers réels des utilisateurs.
"""
from pathlib import Path
from typing import Union

from app import config


def resolve(stored: Union[str, Path]) -> Path:
    """Chemin réel d'un fichier déposé depuis sa valeur en base."""
    if not stored:
        return Path()
    p = Path(stored)
    if p.is_absolute():
        return p
    if p.parts and p.parts[0] == "uploads":
        return config.UPLOAD_DIR / Path(*p.parts[1:])
    return config.UPLOAD_DIR / p


def store(path: Union[str, Path]) -> str:
    """Valeur à persister en base pour un fichier écrit sous UPLOAD_DIR."""
    return str(Path(path).relative_to(config.UPLOAD_DIR)).replace("\\", "/")
