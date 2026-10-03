"""Razorpay and Twilio over plain HTTPS (urllib), so neither SDK is loaded into memory."""

import base64
import hashlib
import hmac
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.cache import bump
from apps.core.tasks import enqueue

from .models import Order, Payment

log = logging.getLogger(__name__)


class ProviderError(Exception):
    pass


def _request(url: str, *, method: str, auth: tuple[str, str], data: bytes | None, content_type: str) -> dict:
    token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Basic {token}", "Content-Type": content_type, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:500].decode(errors="replace")
        raise ProviderError(f"{exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(str(exc.reason)) from exc


# --------------------------------------------------------------------------- Razorpay


def razorpay_create_order(order: Order) -> str:
    result = _request(
        "https://api.razorpay.com/v1/orders",
        method="POST",
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
        data=json.dumps({
            "amount": order.amount_paise,
            "currency": order.currency,
            "receipt": order.public_id,
            "notes": {"order": str(order.pk)},
        }).encode(),
        content_type="application/json",
    )
    return result["id"]


def _hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_checkout_signature(razorpay_order_id: str, payment_id: str, signature: str) -> bool:
    if not settings.RAZORPAY_KEY_SECRET:
        return False
    expected = _hmac_hex(settings.RAZORPAY_KEY_SECRET, f"{razorpay_order_id}|{payment_id}".encode())
    return hmac.compare_digest(expected, signature or "")


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        return False
    return hmac.compare_digest(_hmac_hex(settings.RAZORPAY_WEBHOOK_SECRET, body), signature or "")


def mark_paid(order_id, payment_id: str, *, via: str, amount_paise: int = 0, method: str = "") -> Order:
    """The single place an order becomes paid. Safe to call twice (checkout and webhook)."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status in (Order.PAID, Order.DELIVERED):
            return order
        if amount_paise and amount_paise != order.amount_paise:
            raise ProviderError(f"Amount mismatch for {order}: {amount_paise} != {order.amount_paise}")
        Payment.objects.get_or_create(
            razorpay_payment_id=payment_id,
            defaults={"order": order, "amount_paise": amount_paise or order.amount_paise, "method": method,
                      "verified_via": via},
        )
        order.status = Order.PAID
        order.paid_at = timezone.now()
        order.save(update_fields=["status", "paid_at"])
        pk = str(order.pk)
        transaction.on_commit(lambda: enqueue("orders.fulfil_order", pk))
        # The home page's "photos delivered" stat counts paid orders.
        transaction.on_commit(bump)
    return order


# --------------------------------------------------------------------------- phones & Twilio


def normalise_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:
        digits = "91" + digits
    elif len(digits) == 11 and digits.startswith("0"):
        digits = "91" + digits[1:]
    return f"+{digits}" if 11 <= len(digits) <= 15 else ""


def twilio_send_whatsapp(to: str, variables: dict[str, str], body: str) -> str:
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_WHATSAPP_FROM):
        if settings.DEBUG:
            log.warning("Twilio not configured; would send WhatsApp to %s: %s", to, body)
            return "debug"
        raise ProviderError("Twilio is not configured")
    fields = {
        "From": f"whatsapp:{settings.TWILIO_WHATSAPP_FROM}",
        "To": f"whatsapp:{to}",
        "StatusCallback": f"{settings.API_URL}/api/webhooks/twilio/",
    }
    if settings.TWILIO_CONTENT_SID:
        fields["ContentSid"] = settings.TWILIO_CONTENT_SID
        fields["ContentVariables"] = json.dumps(variables)
    else:
        fields["Body"] = body
    result = _request(
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json",
        method="POST",
        auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        data=urllib.parse.urlencode(fields).encode(),
        content_type="application/x-www-form-urlencoded",
    )
    return result.get("sid", "")


def verify_twilio_signature(url: str, params: dict[str, str], signature: str) -> bool:
    if not settings.TWILIO_AUTH_TOKEN:
        return False
    payload = url + "".join(f"{key}{params[key]}" for key in sorted(params))
    digest = hmac.new(settings.TWILIO_AUTH_TOKEN.encode(), payload.encode(), hashlib.sha1).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), signature or "")
