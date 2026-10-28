"""Charte visuelle : e-mails, affiches et visuels publics (points 11)."""
from types import SimpleNamespace

from app.services import email_branding, job_media, notifications, poster


def _job(**overrides):
    values = {
        "id": 42,
        "title": "Développeur web full-stack",
        "company": "Entreprise Test",
        "location": "Douala",
        "contract_type": "CDI",
        "sector": "Informatique",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_email_html_uses_the_shared_brand_structure():
    html = email_branding.render_html(
        "Votre candidature a été transmise",
        "Bonjour,\n\nVotre candidature a bien été transmise.\n\n"
        "---\nGérer mes préférences e-mail : "
        "https://orientskill.cm/parametres-compte#notifications",
    )

    assert html.startswith("<!doctype html>")
    assert 'lang="fr"' in html
    assert "OrientSkill AI" in html
    assert "Intelligence professionnelle" in html
    assert "#0a6b4c" in html
    assert "#b45309" in html
    assert "max-width:640px" in html
    assert "<img" not in html
    assert "Gérer mes préférences e-mail" in html
    assert "https://orientskill.cm/parametres-compte#notifications" in html
    assert "Votre candidature a bien été transmise." in html


def test_email_html_escapes_untrusted_text_and_links_urls():
    html = email_branding.render_html(
        "Sujet <script>",
        "Texte <script>alert(1)</script> et https://exemple.cm/offre",
    )

    assert "&lt;script&gt;" in html
    assert "<script>" not in html
    assert '<a href="https://exemple.cm/offre"' in html


def test_plain_text_signature_is_added_once():
    first = email_branding.ensure_signature("Corps du message")
    second = email_branding.ensure_signature(first)

    assert first.count("OrientSkill AI · Intelligence professionnelle") == 1
    assert second == first
    assert "http://localhost:5190" in first


def test_smtp_message_contains_plain_text_and_html_alternatives():
    message = notifications._build_message(
        {"from_email": "no-reply@exemple.test", "from_name": "OrientSkill AI"},
        "candidat@exemple.test",
        "Sujet",
        "Corps du message",
        email_branding.render_html("Sujet", "Corps du message"),
        None,
        "",
        "no-reply@exemple.test",
    )

    assert message.get_content_type() == "multipart/alternative"
    plain = message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "Corps du message" in plain
    assert "OrientSkill AI" in html
    assert "#0a6b4c" in html


def test_email_footer_has_signature_and_unsubscribe_link():
    user = SimpleNamespace(id=7, role="candidate")
    footer = notifications.email_footer(user, "new_match")

    assert "OrientSkill AI · Intelligence professionnelle" in footer
    assert "Gérer mes préférences e-mail" in footer
    assert "Se désabonner des alertes emploi" in footer


def test_poster_is_institutional_and_print_friendly():
    svg = poster.build_svg(
        _job(),
        "candidatures@orientskill.test",
        "OS-0042",
        "https://orientskill.cm/postuler/42",
    )

    assert 'width="1200"' in svg and 'height="1500"' in svg
    assert "#f4f7f5" in svg
    assert 'rx="8"' in svg
    assert 'rx="4"' in svg
    assert "#b45309" in svg
    assert "#f5c26b" not in svg
    assert "<circle" not in svg
    assert "linearGradient" not in svg
    assert "candidatures@orientskill.test" in svg


def test_default_job_visual_has_no_decorative_circles():
    svg = job_media.default_svg(
        _job(), "Informatique", "https://orientskill.cm/postuler/42"
    )

    assert 'rx="4"' in svg
    assert 'rx="8"' in svg
    assert "#b45309" in svg
    assert "<circle" not in svg
    assert "radialGradient" not in svg
    assert "OrientSkill AI" in svg
