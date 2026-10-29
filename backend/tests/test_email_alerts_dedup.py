"""Déduplication et seuils des alertes e-mail (§23).

Aucun e-mail réel n'est envoyé : ``dispatch`` est remplacé par un double
factice qui enregistre les appels.
"""
from datetime import datetime, timedelta

from app import models
from app.database import SessionLocal
from app.models import utcnow


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_candidate(db, email, skills, prefs):
    user = models.User(
        email=email,
        full_name="Candidat Alertes",
        password_hash="x",
        role="candidate",
        notification_prefs=prefs,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(
        models.Profile(
            user_id=user.id,
            summary="",
            skills=skills,
            preferences={},
        )
    )
    db.commit()
    return user


def _create_job(db, title, required_skills, days_ahead=1):
    job = models.Job(
        title=title,
        company="Entreprise Test",
        location="Douala",
        sector="Informatique / IT",
        contract_type="CDI",
        description="Offre de test.",
        required_skills=required_skills,
        published_at=utcnow(),
        deadline=utcnow() + timedelta(days=days_ahead),
        source_name="test",
        source_url="https://example.test/offre",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _prefs(**extra):
    base = {
        "email_enabled": True,
        "email": "candidat.alertes@orientskill.cm",
        "email_frequency": "daily",
        "email_min_match": 61,
        "events": {"new_match": True, "expiring": True, "agent": True},
        "role_events_migrated": True,
    }
    base.update(extra)
    return base


def _skill(name, importance="core", proficiency="intermediaire"):
    # ``skill`` est la clé lue dans le profil, ``name`` celle des offres.
    return {
        "skill": name,
        "name": name,
        "importance": importance,
        "proficiency": proficiency,
    }


class FakeDispatch:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return [{"ok": True, "channel": "email", "detail": "ok"}]


def _cleanup(db, *emails):
    for email in emails:
        user = (
            db.query(models.User).filter(models.User.email == email).first()
        )
        if user:
            db.query(models.NotificationLog).filter(
                models.NotificationLog.user_id == user.id
            ).delete(synchronize_session=False)
            db.query(models.Profile).filter(
                models.Profile.user_id == user.id
            ).delete(synchronize_session=False)
            db.query(models.User).filter(models.User.id == user.id).delete(
                synchronize_session=False
            )
    db.query(models.Job).filter(
        models.Job.source_name == "test"
    ).delete(synchronize_session=False)
    db.commit()


def test_digest_email_threshold_strictly_above_60(client):
    db = next(_db())
    try:
        user = _create_candidate(
            db,
            "digest.seuil@orientskill.cm",
            [_skill("Python", proficiency="debutant")],
            _prefs(),
        )
        job = _create_job(
            db, "Dev Python débutant", [_skill("Python", importance="core")]
        )
        import app.services.digest as digest_mod

        original = digest_mod.dispatch
        fake = FakeDispatch()
        digest_mod.dispatch = fake
        try:
            now = utcnow().replace(hour=9)
            result = digest_mod.run_digest_for_user(db, user, now=now)
            assert result["notified"] == 0, result
            assert fake.calls == [], "aucun e-mail à 50 %"
            assert (
                db.query(models.NotificationLog)
                .filter_by(user_id=user.id, event="new_match")
                .count()
                == 0
            )
        finally:
            digest_mod.dispatch = original
    finally:
        _cleanup(db, "digest.seuil@orientskill.cm")
        db.close()


def test_digest_dedup_user_job(client):
    db = next(_db())
    try:
        user = _create_candidate(
            db,
            "digest.dedup@orientskill.cm",
            [_skill("Python")],
            _prefs(),
        )
        job = _create_job(db, "Dev Python confirmé", [_skill("Python")])
        import app.services.digest as digest_mod

        original = digest_mod.dispatch
        fake = FakeDispatch()
        digest_mod.dispatch = fake
        try:
            now = utcnow().replace(hour=9)
            first = digest_mod.run_digest_for_user(db, user, now=now)
            assert first["notified"] == 1, first
            assert len(fake.calls) == 1
            logged = (
                db.query(models.NotificationLog)
                .filter_by(user_id=user.id, event="new_match", job_id=job.id)
                .count()
            )
            assert logged == 1

            second = digest_mod.run_digest_for_user(db, user, now=now)
            assert second["notified"] == 0, second
            assert second["skipped"] == 1
            assert len(fake.calls) == 1, "pas de nouvel envoi pour le même job"
        finally:
            digest_mod.dispatch = original
    finally:
        _cleanup(db, "digest.dedup@orientskill.cm")
        db.close()
def test_daily_cap_shared_by_job_alerts(client):
    db = next(_db())
    try:
        user = _create_candidate(
            db,
            "digest.cap@orientskill.cm",
            [_skill("Python")],
            _prefs(),
        )
        job_match = _create_job(db, "Dev Python cap", [_skill("Python")])
        job_expiring = _create_job(
            db, "Dev Python urgent", [_skill("Python")], days_ahead=0
        )
        fake_digest = FakeDispatch()
        fake_alerts = FakeDispatch()
        import app.services.alerts as alerts_mod
        import app.services.digest as digest_mod

        orig_digest, orig_alerts = digest_mod.dispatch, alerts_mod.dispatch
        digest_mod.dispatch = fake_digest
        alerts_mod.dispatch = fake_alerts
        try:
            now = utcnow().replace(hour=9)
            first = digest_mod.run_digest_for_user(db, user, now=now)
            assert first["notified"] == 1, first

            # Même passe, même jour : l'échéance ne doit pas renvoyer d'e-mail.
            result = alerts_mod.run_alerts_once(db)
            assert fake_alerts.calls == [], fake_alerts.calls
            assert result["notified"] == 0, result
        finally:
            digest_mod.dispatch = orig_digest
            alerts_mod.dispatch = orig_alerts
    finally:
        _cleanup(db, "digest.cap@orientskill.cm")
        db.close()


def test_job_alert_sent_today(client):
    db = next(_db())
    try:
        user = _create_candidate(
            db,
            "digest.capcheck@orientskill.cm",
            [_skill("Python")],
            _prefs(),
        )
        db.add(
            models.NotificationLog(
                user_id=user.id,
                event="new_match",
                job_id=1,
                sent_at=utcnow(),
            )
        )
        db.add(
            models.NotificationLog(
                user_id=user.id,
                event="agent",
                job_id=None,
                sent_at=utcnow() - timedelta(days=2),
            )
        )
        db.commit()
        from app.services.notifications import job_alert_sent_today

        assert job_alert_sent_today(db, user.id) is True
        assert job_alert_sent_today(db, 999999) is False
    finally:
        db.query(models.NotificationLog).delete()
        db.commit()
        db.close()


def test_profile_notifications_email_min_match_validation(client, admin_headers):
    # Sous le seuil (60) : refusé.
    response = client.put(
        "/api/profile/notifications",
        json={"email_min_match": 60},
        headers=admin_headers,
    )
    assert response.status_code == 422, response.text

    # Seuil autorisé (61).
    response = client.put(
        "/api/profile/notifications",
        json={"email_min_match": 61},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["email_min_match"] == 61, response.text