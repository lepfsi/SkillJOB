"""Planificateur de collecte autonome des sources RSS/JSON.

Chaque source activée possède son propre intervalle. Le thread daemon
vérifie périodiquement les sources échues et délègue la collecte au
service d'ingestion, qui télécharge en parallèle et écrit de façon
séquentielle. Le planificateur est désactivable par configuration
(``SOURCE_SCHEDULER_ENABLED=0``), notamment dans les tests.
"""
import logging
import threading
from typing import Optional

from app import config
from app.database import SessionLocal
from app.services import ingestion

logger = logging.getLogger("orientskill.sources")


class SourceScheduler:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        if not config.SOURCE_SCHEDULER_ENABLED:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="orientskill-sources", daemon=True
        )
        self._thread.start()

    def _loop(self) -> None:
        # Petit délai initial : laisse l'application finir son démarrage.
        self._stop.wait(15)
        while not self._stop.is_set():
            db = SessionLocal()
            try:
                results = ingestion.run_due_sources(db)
                if results:
                    imported = sum(item.get("imported", 0) for item in results)
                    errors = sum(1 for item in results if item.get("error"))
                    logger.info(
                        "Collecte autonome : %s source(s), %s offre(s), %s échec(s)",
                        len(results), imported, errors,
                    )
            except Exception as exc:  # pragma: no cover - défense
                logger.warning("Collecte autonome interrompue : %s", exc)
            finally:
                db.close()
            self._stop.wait(config.SOURCE_SCHEDULER_TICK_SECONDS)

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None


source_scheduler = SourceScheduler()
