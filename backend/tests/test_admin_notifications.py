"""Régression boîte de notifications admin (§21).

Insère directement des journaux d'alertes (sans e-mail réel) et vérifie la
liste, les compteurs, le marquage lu, l'archivage et la suppression.
"""
from datetime import timedelta

from app import models
from app.database import SessionLocal
from app.models import utcnow


def _admin_headers(client):
    login = client.post("/api/auth/login", json={
        "email": "admin@orientskill.cm", "password": "admin1234",
    })
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['token']}"}


def _insert_logs(db):
    now = utcnow()
    rows = [
        models.AdminNotificationLog(
            category="verification",
            subject="Pièce d'identité à examiner",
            body="Candidat.demo demande la vérification de son profil.",
            recipients=["admin@orientskill.cm"],
            sent_count=1,
            failed_count=0,
            created_at=now,
        ),
        models.AdminNotificationLog(
            category="report",
            subject="Offre signalée",
            body="Une offre est signalée comme expirée.",
            recipients=["admin@orientskill.cm"],
            sent_count=0,
            failed_count=1,
            created_at=now - timedelta(hours=2),
            marked_read_at=now - timedelta(hours=1),
        ),
        models.AdminNotificationLog(
            category="ingestion",
            subject="Échec de collecte",
            body="La source X ne répond plus.",
            recipients=["admin@orientskill.cm"],
            sent_count=0,
            failed_count=0,
            created_at=now - timedelta(hours=4),
            archived_at=now - timedelta(hours=3),
        ),
    ]
    for row in rows:
        db.add(row)
    db.commit()
    return rows[0].id, rows[1].id


def test_admin_notifications_list_stats_read_archive_delete(client):
    headers = _admin_headers(client)
    db = SessionLocal()
    try:
        unread_id, read_id = _insert_logs(db)

        response = client.get("/api/admin/notifications", headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total"] == 2
        assert data["unread"] == 1
        assert {item["id"] for item in data["items"]} == {unread_id, read_id}
        unread_item = next(i for i in data["items"] if i["id"] == unread_id)
        assert unread_item["is_unread"] is True
        assert unread_item["href"] == "/admin/verifications"
        read_item = next(i for i in data["items"] if i["id"] == read_id)
        assert read_item["is_unread"] is False

        stats = client.get("/api/admin/notifications/stats", headers=headers).json()
        assert stats["total"] == 2
        assert stats["unread"] == 1
        assert stats["per_category"]["verification"]["total"] == 1

        mark = client.post(f"/api/admin/notifications/{unread_id}/mark-read", headers=headers)
        assert mark.status_code == 200, mark.text
        stats = client.get("/api/admin/notifications/stats", headers=headers).json()
        assert stats["unread"] == 0

        archive = client.put(f"/api/admin/notifications/{read_id}/mark-deleted", headers=headers)
        assert archive.status_code == 200, archive.text
        remaining = client.get("/api/admin/notifications", headers=headers).json()
        assert remaining["total"] == 1
        assert remaining["items"][0]["id"] == unread_id

        deleted = client.delete(f"/api/admin/notifications/{unread_id}", headers=headers)
        assert deleted.status_code == 200, deleted.text
        empty = client.get("/api/admin/notifications", headers=headers).json()
        assert empty["total"] == 0
        assert empty["items"] == []
    finally:
        db.query(models.AdminNotificationLog).delete()
        db.commit()
        db.close()
