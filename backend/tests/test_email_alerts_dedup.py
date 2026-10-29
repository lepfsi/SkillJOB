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


def _create_job(db, title, required_skills, days_ahead=1, company_id=None):
    job = models.Job(
        title=title,
        company="Entreprise Test",
        company_id=company_id,
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


def _create_recruiter(db, email, prefs):
    user = models.User(
        email=email,
        full_name="Recruteur Alertes",
        password_hash="x",
        role="recruiter",
        notification_prefs=prefs,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    company = models.Company(
        owner_user_id=user.id,
        name="Entreprise Alertes",
        sector="Informatique / IT",
        location="Douala",
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return user, company


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


def test_alerts_one_email_per_candidate_pass(client):
    db = next(_db())
    try:
        user = _create_candidate(
            db,
            "alerts.cap.candidat@orientskill.cm",
            [_skill("Python")],
            _prefs(),
        )
        _create_job(
            db, "Dev Python urgent A", [_skill("Python")], days_ahead=1
        )
        _create_job(
            db, "Dev Python urgent B", [_skill("Python")], days_ahead=2
        )
        import app.services.alerts as alerts_mod

        original = alerts_mod.dispatch
        fake = FakeDispatch()
        alerts_mod.dispatch = fake
        try:
            alerts_mod.run_alerts_once(db)
            calls = [c for c in fake.calls if c["args"][1].id == user.id]
            assert len(calls) == 1, calls
            assert "expire bientôt" in calls[0]["args"][2]
            events = [
                log.event
                for log in db.query(models.NotificationLog)
                .filter_by(user_id=user.id)
                .all()
            ]
            assert events == ["expiring"], events
        finally:
            alerts_mod.dispatch = original
    finally:
        _cleanup(db, "alerts.cap.candidat@orientskill.cm")
        db.close()


def test_expiring_email_respects_min_match(client):
    db = next(_db())
    try:
        user = _create_candidate(
            db,
            "alerts.seuil.expiration@orientskill.cm",
            [_skill("Python", proficiency="avance")],
            _prefs(
                email_min_match=70,
                events={"expiring": True, "agent": False},
            ),
        )
        _create_job(
            db,
            "Dev Python partiel",
            [
                _skill("Python", importance="core"),
                _skill("SQL", importance="preferred"),
            ],
            days_ahead=1,
        )
        import app.services.alerts as alerts_mod

        original = alerts_mod.dispatch
        fake = FakeDispatch()
        alerts_mod.dispatch = fake
        try:
            alerts_mod.run_alerts_once(db)
            calls = [c for c in fake.calls if c["args"][1].id == user.id]
            assert calls == [], "seuil 70 : le match à 67 % reste in-app"

            prefs = dict(user.notification_prefs)
            prefs["email_min_match"] = 61
            user.notification_prefs = prefs
            db.commit()

            alerts_mod.run_alerts_once(db)
            calls = [c for c in fake.calls if c["args"][1].id == user.id]
            assert len(calls) == 1, calls
            assert "expire bientôt" in calls[0]["args"][2]
        finally:
            alerts_mod.dispatch = original
    finally:
        _cleanup(db, "alerts.seuil.expiration@orientskill.cm")
        db.close()


def test_alerts_one_email_per_recruiter_pass(client):
    db = next(_db())
    recruiter = company = None
    try:
        recruiter, company = _create_recruiter(
            db,
            "alerts.cap.recruteur@orientskill.cm",
            _prefs(
                email="recruteur.alertes@orientskill.cm",
                events={"job_expiring": True},
            ),
        )
        _create_job(
            db, "Offre urgente A", [_skill("Python")],
            days_ahead=1, company_id=company.id,
        )
        _create_job(
            db, "Offre urgente B", [_skill("Python")],
            days_ahead=2, company_id=company.id,
        )
        import app.services.alerts as alerts_mod

        original = alerts_mod.dispatch
        fake = FakeDispatch()
        alerts_mod.dispatch = fake
        try:
            alerts_mod.run_alerts_once(db)
            calls = [
                c for c in fake.calls if c["args"][1].id == recruiter.id
            ]
            assert len(calls) == 1, calls
            assert "expire bientôt" in calls[0]["args"][2]
            events = [
                log.event
                for log in db.query(models.NotificationLog)
                .filter_by(user_id=recruiter.id)
                .all()
            ]
            assert events == ["job_expiring"], events
        finally:
            alerts_mod.dispatch = original
    finally:
        if recruiter is not None:
            db.query(models.NotificationLog).filter_by(
                user_id=recruiter.id
            ).delete(synchronize_session=False)
        if company is not None:
            db.query(models.Job).filter(
                models.Job.company_id == company.id
            ).delete(synchronize_session=False)
            db.query(models.Company).filter_by(id=company.id).delete(
                synchronize_session=False
            )
        if recruiter is not None:
            db.query(models.User).filter_by(id=recruiter.id).delete(
                synchronize_session=False
            )
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