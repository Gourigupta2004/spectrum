import hashlib
import hmac
import json
from unittest import mock

from django.core import mail
from django.test import override_settings

from apps.orders.models import Delivery, Order, Payment

from .base import SpectrumTestCase


def sign(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


class OrderTests(SpectrumTestCase):
    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.photos = [self.photo(self.event, f"P{i}", i) for i in range(3)]

    def create(self, **overrides):
        body = {"eventSlug": "annual-day", "photoIds": [str(self.photos[0].pk), str(self.photos[1].pk), "999"],
                "name": "Asha", "phone": "98100 44120", "email": "asha@example.com", "deliverVia": "email",
                "idempotencyKey": "key-1-aaaaaaaaaaaaaaaa", **overrides}
        ids = iter(f"order_RZP{i}" for i in range(Order.objects.count() + 1, 100))
        with mock.patch("apps.orders.views.razorpay_create_order", side_effect=lambda order: next(ids)):
            return self.client.post("/api/orders/", json.dumps(body), content_type="application/json")

    def test_price_is_computed_on_the_server_and_idempotent(self):
        first = self.create().json()
        self.assertEqual(first["amount"], 58)
        self.assertEqual(first["razorpay"]["orderId"], "order_RZP1")
        self.assertEqual(self.create().json()["id"], first["id"])
        bundle = self.create(bundle=True, idempotencyKey="key-2-aaaaaaaaaaaaaaaa").json()
        self.assertEqual(bundle["amount"], 299)
        self.assertEqual(Order.objects.count(), 2)

    def test_videos_are_priced_and_downloadable(self):
        clip = self.video(self.event, "Highlights")
        order = self.create(videoIds=[str(clip.pk), "999"], idempotencyKey="key-v-aaaaaaaaaaaaaaaa").json()
        self.assertEqual(order["amount"], 58 + 199)  # two photos + one video
        bundle = self.create(bundle=True, videoIds=[str(clip.pk)], idempotencyKey="key-w-aaaaaaaaaaaaaaaa").json()
        self.assertEqual(bundle["amount"], 299 + 199)  # full album + the video on top

        signature = sign("secret", b"order_RZP1|pay_1")
        with self.captureOnCommitCallbacks(execute=True):
            paid = self.client.post(f"/api/orders/{order['id']}/verify/", json.dumps({
                "razorpayOrderId": "order_RZP1", "razorpayPaymentId": "pay_1", "razorpaySignature": signature}),
                content_type="application/json").json()
        self.assertEqual(paid["status"], "paid")
        db_order = Order.objects.exclude(status=Order.CREATED).get()
        body = mail.outbox[0].body
        item = db_order.items.get(video__isnull=False)
        video_path = f"/api/downloads/{db_order.download_token}/photos/{item.pk}/"
        self.assertIn(f"/api/downloads/{db_order.download_token}/zip/", body)
        self.assertIn(video_path, body)
        self.assertIn("one-time", body)

        # The video link works exactly once.
        first = self.client.get(video_path)
        self.assertEqual(first.status_code, 200)
        self.assertIn(".mp4", first["Content-Disposition"])
        self.assertEqual(self.client.get(video_path).status_code, 410)

    def test_whatsapp_requires_valid_phone(self):
        response = self.create(phone="12", deliverVia="whatsapp", idempotencyKey="key-3-aaaaaaaaaaaaaaaa")
        self.assertEqual(response.status_code, 400)

    def test_verify_rejects_bad_signature(self):
        order = self.create().json()
        response = self.client.post(f"/api/orders/{order['id']}/verify/", json.dumps({
            "razorpayOrderId": "order_RZP1", "razorpayPaymentId": "pay_1", "razorpaySignature": "nope"}),
            content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_paid_order_is_delivered_and_downloadable(self):
        order = self.create().json()
        signature = sign("secret", b"order_RZP1|pay_1")
        with self.captureOnCommitCallbacks(execute=True):
            paid = self.client.post(f"/api/orders/{order['id']}/verify/", json.dumps({
                "razorpayOrderId": "order_RZP1", "razorpayPaymentId": "pay_1", "razorpaySignature": signature}),
                content_type="application/json").json()
        self.assertEqual(paid["status"], "paid")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(Delivery.objects.get().status, Delivery.SENT)
        db_order = Order.objects.get()
        self.assertEqual(db_order.status, Order.DELIVERED)

        # The email links straight to the photos zip; the zip is built before sending.
        self.assertTrue(db_order.zip_file)
        zip_path = f"/api/downloads/{db_order.download_token}/zip/"
        self.assertIn(zip_path, mail.outbox[0].body)
        file_response = self.client.get(zip_path)
        self.assertEqual(file_response.status_code, 200)
        self.assertIn("attachment", file_response["Content-Disposition"])
        self.assertEqual(self.client.get("/api/downloads/not-a-token/zip/").status_code, 404)

    def test_webhook_is_verified_and_deduplicated(self):
        order = self.create(bundle=True, idempotencyKey="key-9-aaaaaaaaaaaaaaaa").json()
        body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {
            "id": "pay_9", "order_id": "order_RZP1", "amount": 29900, "method": "upi"}}}}).encode()
        headers = {"HTTP_X_RAZORPAY_SIGNATURE": sign("hooksecret", body), "HTTP_X_RAZORPAY_EVENT_ID": "evt_1"}
        self.assertEqual(self.client.post("/api/webhooks/razorpay/", body, content_type="application/json",
                                          HTTP_X_RAZORPAY_SIGNATURE="bad").status_code, 400)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post("/api/webhooks/razorpay/", body, content_type="application/json", **headers)
        self.client.post("/api/webhooks/razorpay/", body, content_type="application/json", **headers)
        self.assertEqual(Payment.objects.count(), 1)
        paid = Order.objects.get(pk=order["id"])
        self.assertIn(paid.status, (Order.PAID, Order.DELIVERED))
        self.assertEqual(paid.items.count(), 3)  # bundle expanded to every ready photo

    @override_settings(PAYMENTS_MOCK=True)
    def test_mock_mode(self):
        order = self.create(idempotencyKey="key-m-aaaaaaaaaaaaaaaa").json()
        self.assertTrue(order["mock"])
        paid = self.client.post(f"/api/orders/{order['id']}/verify/", json.dumps({"mock": True}),
                                content_type="application/json").json()
        self.assertEqual(paid["status"], "paid")


class OrderHardeningTests(OrderTests):
    def test_idempotency_key_is_bound_to_the_buyer(self):
        first = self.create().json()
        other = self.create(phone="9999988888").json()  # same key, different buyer
        self.assertNotEqual(first["id"], other["id"])

    def test_bad_photo_ids_are_a_400(self):
        self.assertEqual(self.create(photoIds={"a": 1}, idempotencyKey="k-bad-aaaaaaaaaaaaaaaa").status_code, 400)

    def test_twilio_callback_without_sid_changes_nothing(self):
        from apps.orders import views

        with mock.patch.object(views, "verify_twilio_signature", return_value=True):
            self.client.post("/api/webhooks/twilio/", {"MessageStatus": "failed"})
        self.assertFalse(Delivery.objects.filter(status=Delivery.FAILED).exists())
