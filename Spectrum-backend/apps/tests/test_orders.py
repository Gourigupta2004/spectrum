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
        # Email-only by default: a filled field now IS the delivery channel, and
        # the test environment has no Twilio to take a WhatsApp send.
        body = {"eventSlug": "annual-day", "photoIds": [str(self.photos[0].pk), str(self.photos[1].pk), "999"],
                "name": "Asha", "phone": "", "email": "asha@example.com",
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

    def test_not_for_sale_event_shows_but_takes_no_orders(self):
        self.event.not_for_sale = True
        self.event.save()
        detail = self.client.get("/api/events/annual-day/").json()
        self.assertTrue(detail["event"]["notForSale"])
        self.assertIn("not available for sale", detail["copy"]["notForSaleMessage"])  # editable in the admin
        self.assertTrue(detail["photos"], "the gallery itself still shows")
        response = self.create()
        self.assertEqual(response.status_code, 403)
        self.assertIn("not available for sale", response.json()["error"])
        self.assertEqual(Order.objects.count(), 0)
        # Back on sale, orders work again.
        self.event.not_for_sale = False
        self.event.save()
        self.assertEqual(self.create().status_code, 200)

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

        # Opening the link (as an email scanner or chat preview would) only shows
        # the page; pressing Download takes the file, exactly once.
        for _ in range(2):
            page = self.client.get(video_path)
            self.assertEqual(page.status_code, 200)
            self.assertNotIn("Content-Disposition", page)
            self.assertIn("Your download is ready", page.content.decode())
        first = self.client.post(video_path)
        self.assertEqual(first.status_code, 200)
        self.assertIn(".mp4", first["Content-Disposition"])
        self.assertEqual(self.client.post(video_path).status_code, 410)
        used = self.client.get(video_path)
        self.assertEqual(used.status_code, 410)
        self.assertIn("already been used", used.content.decode())

    def test_whatsapp_requires_valid_phone(self):
        response = self.create(phone="12", idempotencyKey="key-3-aaaaaaaaaaaaaaaa")
        self.assertEqual(response.status_code, 400)

    def test_some_contact_is_required(self):
        response = self.create(phone="", email="", idempotencyKey="key-4-aaaaaaaaaaaaaaaa")
        self.assertEqual(response.status_code, 400)

    def test_both_channels_when_both_given(self):
        order = self.create(phone="98100 44120", idempotencyKey="key-5-aaaaaaaaaaaaaaaa").json()
        from apps.orders.models import Order as O
        db = O.objects.get(pk=order["id"])
        self.assertTrue(db.deliver_whatsapp)
        self.assertTrue(db.deliver_email)

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
        self.assertIn("one-time", mail.outbox[0].body)
        page = self.client.get(zip_path)
        self.assertNotIn("Content-Disposition", page)
        self.assertIn("2 photos from Annual Day", page.content.decode())
        file_response = self.client.post(zip_path)
        self.assertEqual(file_response.status_code, 200)
        self.assertIn("attachment", file_response["Content-Disposition"])
        self.assertEqual(self.client.post(zip_path).status_code, 410, "the zip link is one-time too")
        self.assertEqual(self.client.get("/api/downloads/not-a-token/zip/").status_code, 404)

        # A download that broke halfway: the team issues fresh links, the old ones die.
        from apps.orders.services import reissue_download_links

        old_token = db_order.download_token
        with self.captureOnCommitCallbacks(execute=True):
            reissue_download_links(db_order)
        db_order.refresh_from_db()
        self.assertNotEqual(db_order.download_token, old_token)
        self.assertEqual(self.client.post(zip_path).status_code, 404, "the old link no longer works")
        new_path = f"/api/downloads/{db_order.download_token}/zip/"
        self.assertIn(new_path, mail.outbox[-1].body, "the new link is sent again")
        self.assertEqual(self.client.post(new_path).status_code, 200)

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

    def pay_with_sends_failing(self, **overrides):
        """A paid order whose WhatsApp and email sends both fail, as before a
        WhatsApp sender or mailbox is set up."""
        order = self.create(**overrides).json()
        with mock.patch("apps.orders.services.twilio_send_whatsapp", side_effect=RuntimeError("no sender")), \
                mock.patch("apps.orders.jobs.EmailMultiAlternatives.send", side_effect=RuntimeError("no mailbox")), \
                self.captureOnCommitCallbacks(execute=True):
            try:
                self.client.post(f"/api/orders/{order['id']}/verify/", json.dumps({
                    "razorpayOrderId": "order_RZP1", "razorpayPaymentId": "pay_1",
                    "razorpaySignature": sign("secret", b"order_RZP1|pay_1")}), content_type="application/json")
            except RuntimeError:
                pass  # eager jobs re-raise the failed send
        db_order = Order.objects.get()
        self.assertEqual(db_order.status, Order.PAID)
        self.client.force_login(self.make_staff())
        return db_order

    def by_hand(self, action, order, **extra):
        return self.client.post("/admin/orders/order/", {"action": action, "_selected_action": [str(order.pk)], **extra})

    def test_sending_by_hand_shows_each_message_and_marks_it_sent(self):
        from urllib.parse import quote

        db_order = self.pay_with_sends_failing(phone="98765 43210")
        zip_path = quote(f"/api/downloads/{db_order.download_token}/zip/", safe="")

        page = self.by_hand("send_whatsapp_by_hand", db_order)
        self.assertContains(page, "https://web.whatsapp.com/send?phone=919876543210&amp;text=")
        self.assertContains(page, "https://wa.me/919876543210?text=")
        self.assertContains(page, zip_path)
        self.assertIsNone(Order.objects.get().zip_used_at, "showing the message uses nothing up")
        self.assertEqual(self.by_hand("send_whatsapp_by_hand", db_order, confirm="1",
                                      sent=[str(db_order.pk)]).status_code, 302)
        whatsapp = Delivery.objects.get(channel=Delivery.WHATSAPP)
        self.assertEqual((whatsapp.status, whatsapp.provider_message_id), (Delivery.SENT, "manual"))
        self.assertEqual(Order.objects.get().status, Order.PAID, "the email hasn't gone yet")

        page = self.by_hand("send_email_by_hand", db_order)
        self.assertContains(page, "Your memories from Annual Day are ready")
        self.assertContains(page, "https://mail.google.com/mail/?view=cm&amp;fs=1&amp;to=asha%40example.com")
        self.assertContains(page, "mailto:asha@example.com?subject=")
        self.assertContains(page, zip_path)
        self.by_hand("send_email_by_hand", db_order, confirm="1", sent=[str(db_order.pk)])
        self.assertEqual(Delivery.objects.get(channel=Delivery.EMAIL).status, Delivery.SENT)
        self.assertEqual(Order.objects.get().status, Order.DELIVERED)

    def test_mark_delivered_closes_the_order_and_its_failed_sends(self):
        db_order = self.pay_with_sends_failing(phone="98765 43210")
        self.assertEqual(self.by_hand("mark_delivered", db_order).status_code, 302)
        self.assertEqual(Order.objects.get().status, Order.DELIVERED)
        self.assertEqual(set(Delivery.objects.values_list("status", flat=True)), {Delivery.SENT})

    @override_settings(TWILIO_ACCOUNT_SID="AC1", TWILIO_AUTH_TOKEN="t", TWILIO_WHATSAPP_FROM="+919667041123",
                       TWILIO_CONTENT_SID="HX1")
    def test_whatsapp_template_gets_the_same_details_as_the_plain_message(self):
        from urllib.parse import parse_qs

        order = self.create(phone="98765 43210", email="").json()
        sent = []

        def twilio(url, *, data, **kwargs):
            sent.append(parse_qs(data.decode()))
            return {"sid": "SM1"}

        with mock.patch("apps.orders.services._request", side_effect=twilio), \
                self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/api/orders/{order['id']}/verify/", json.dumps({
                "razorpayOrderId": "order_RZP1", "razorpayPaymentId": "pay_1",
                "razorpaySignature": sign("secret", b"order_RZP1|pay_1")}), content_type="application/json")
        db_order = Order.objects.get()
        self.assertEqual(db_order.status, Order.DELIVERED)
        self.assertEqual(sent[0]["ContentSid"], ["HX1"])
        self.assertEqual(json.loads(sent[0]["ContentVariables"][0]), {
            "1": "Asha", "2": f"Annual Day ({db_order.event.institution.name})", "3": "2 photos (zip)",
            "4": f"http://localhost:8000/api/downloads/{db_order.download_token}/zip/", "5": db_order.public_id})

    def test_twilio_callback_without_sid_changes_nothing(self):
        from apps.orders import views

        with mock.patch.object(views, "verify_twilio_signature", return_value=True):
            self.client.post("/api/webhooks/twilio/", {"MessageStatus": "failed"})
        self.assertFalse(Delivery.objects.filter(status=Delivery.FAILED).exists())
