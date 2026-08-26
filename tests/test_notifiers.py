from unittest.mock import MagicMock, patch

from watch_hunter.models import ConditionGrade, Listing, SearchCriteria
from watch_hunter.notifier.console import ConsoleNotifier
from watch_hunter.notifier.email_resend import ResendNotifier
from watch_hunter.notifier.email_smtp import SmtpNotifier
from watch_hunter.notifier.formatter import EmailFormatter


def create_sample_listing() -> Listing:
    return Listing(
        id="ebay:123",
        title="Omega Aqua Terra 231.10.39.21.02.002",
        price=2900.0,
        currency="EUR",
        price_eur=2900.0,
        condition="Excellent",
        condition_grade=ConditionGrade.EXCELLENT,
        seller="trusted_dealer",
        source="ebay",
        url="https://ebay.com/itm/123",
        matched_reference="231.10.39.21.02.002",
        location="DE",
    )


def test_email_formatter() -> None:
    criteria = SearchCriteria()
    listing = create_sample_listing()

    subject = EmailFormatter.format_subject(1)
    assert "1 New Omega Aqua Terra Match" in subject

    text = EmailFormatter.format_text([listing], criteria)
    assert "231.10.39.21.02.002" in text
    assert "2,900.00 EUR" in text
    assert "https://ebay.com/itm/123" in text

    html_content = EmailFormatter.format_html([listing], criteria)
    assert "Watch Hunter Daily Digest" in html_content
    assert "231.10.39.21.02.002" in html_content
    assert 'href="https://ebay.com/itm/123"' in html_content


def test_resend_notifier_send() -> None:
    notifier = ResendNotifier(api_key="mock_resend_key")
    assert notifier.is_configured() is True

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "resend_email_id_123"}

    with patch("requests.post", return_value=mock_resp) as mock_post:
        success = notifier.send_digest([create_sample_listing()], "2alex.garcia2@gmail.com")
        assert success is True
        mock_post.assert_called_once()
        call_json = mock_post.call_args[1]["json"]
        assert call_json["to"] == ["2alex.garcia2@gmail.com"]
        assert "Omega Aqua Terra" in call_json["subject"]


def test_resend_notifier_empty_listings() -> None:
    notifier = ResendNotifier(api_key="mock_resend_key")
    assert notifier.send_digest([], "2alex.garcia2@gmail.com") is True


def test_smtp_notifier_send() -> None:
    notifier = SmtpNotifier(
        host="smtp.example.com",
        port=587,
        user="testuser",
        password="testpassword",
    )
    assert notifier.is_configured() is True

    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server
        mock_server.__enter__.return_value = mock_server

        success = notifier.send_digest([create_sample_listing()], "2alex.garcia2@gmail.com")
        assert success is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("testuser", "testpassword")
        mock_server.sendmail.assert_called_once()


def test_console_notifier() -> None:
    notifier = ConsoleNotifier()
    assert notifier.is_configured() is True
    assert notifier.send_digest([create_sample_listing()], "2alex.garcia2@gmail.com") is True
