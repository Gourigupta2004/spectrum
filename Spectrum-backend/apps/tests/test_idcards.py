import hashlib
import hmac
import json
from unittest import mock

from django.core.exceptions import ValidationError

from apps.idcards.models import DuplicateIdCardRequest

from .base import SpectrumTestCase


def sign(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


class DuplicateIdCardTests(SpectrumTestCase):
    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.institution.offers_duplicate_id_cards = True
        self.institution.duplicate_id_card_price = 150
        self.institution.save()

    def create(self, **overrides):
        body = {"institutionId": "dps", "studentName": "Asha Rao", "className": "7B", "admissionNo": "A-1042",
                "email": "asha@example.com", "phone": "98100 44120", "idempotencyKey": "key-1-aaaaaaaaaaaaaaaa",
                **overrides}
        ids = iter(f"order_ID{i}" for i in range(DuplicateIdCardRequest.objects.count() + 1, 100))
        with mock.patch("apps.idcards.views.razorpay_create_order", side_effect=lambda card: next(ids)):
            return self.client.post("/api/idcards/duplicate/", json.dumps(body), content_type="application/json")

    def test_page_lists_only_institutions_that_offer_the_service(self):
        data = self.client.get("/api/pages/id-card/").json()
        self.assertEqual(data["institutions"], [{"id": "dps", "name": "Delhi Public School", "price": 150}])
        self.assertEqual(data["copy"]["guidelinesTitle"], "Before You Request")
        # A price change shows straight away (the page cache is invalidated).
        self.institution.duplicate_id_card_price = 175
        self.institution.save()
        self.assertEqual(self.client.get("/api/pages/id-card/").json()["institutions"][0]["price"], 175)
        self.assertEqual(self.client.get("/api/site/").json()["copy"]["navIdCard"], "ID Card")

    def test_offering_needs_a_price(self):
        self.other.offers_duplicate_id_cards = True
        with self.assertRaises(ValidationError):
            self.other.full_clean()

    def test_price_comes_from_the_institution_and_requests_are_idempotent(self):
        first = self.create(price=1).json()  # a price sent by the browser is ignored
        self.assertEqual(first["amount"], 150)
        self.assertEqual(first["razorpay"]["orderId"], "order_ID1")
        self.assertEqual(self.create().json()["id"], first["id"])
        card = DuplicateIdCardRequest.objects.get()
        self.assertEqual((card.student_name, card.class_name, card.admission_no, card.phone),
                         ("Asha Rao", "7B", "A-1042", "+919810044120"))

    def test_institutions_without_the_service_and_missing_fields_are_refused(self):
        self.assertEqual(self.create(institutionId="doon").json()["field"], "institutionId")
        self.assertEqual(self.create(admissionNo="").json()["field"], "admissionNo")
        self.assertEqual(self.create(email="nope").json()["field"], "email")
        self.assertEqual(self.create(phone="123").json()["field"], "phone")
        self.assertFalse(DuplicateIdCardRequest.objects.exists())

    def test_checkout_signature_marks_the_request_paid(self):
        created = self.create().json()
        url = f"/api/idcards/duplicate/{created['id']}/verify/"
        bad = self.client.post(url, json.dumps({"razorpayOrderId": "order_ID1", "razorpayPaymentId": "pay_1",
                                                "razorpaySignature": "forged"}), content_type="application/json")
        self.assertEqual(bad.status_code, 400)
        paid = self.client.post(url, json.dumps({
            "razorpayOrderId": "order_ID1", "razorpayPaymentId": "pay_1",
            "razorpaySignature": sign("secret", b"order_ID1|pay_1")}), content_type="application/json").json()
        self.assertTrue(paid["paid"])
        card = DuplicateIdCardRequest.objects.get()
        self.assertEqual((card.status, card.razorpay_payment_id, card.paid_via), ("paid", "pay_1", "client"))

    def test_webhook_marks_the_request_paid(self):
        self.create()
        body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {
            "id": "pay_9", "order_id": "order_ID1", "amount": 15000, "method": "upi"}}}}).encode()
        response = self.client.post("/api/webhooks/razorpay/", body, content_type="application/json",
                                    HTTP_X_RAZORPAY_SIGNATURE=sign("hooksecret", body))
        self.assertEqual(response.status_code, 200)
        card = DuplicateIdCardRequest.objects.get()
        self.assertEqual((card.status, card.paid_via), ("paid", "webhook"))

    def test_admin_table_lists_requests(self):
        self.create()
        self.client.force_login(self.make_staff())
        html = self.client.get("/admin/idcards/duplicateidcardrequest/").content.decode()
        for value in ("Asha Rao", "7B", "A-1042", "Delhi Public School", "₹150", "Awaiting payment"):
            self.assertIn(value, html)
        self.assertIn("ID cards", self.client.get("/admin/").content.decode())


class DuplicateIdCardAdminTests(SpectrumTestCase):
    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.client.force_login(self.make_staff())

    def request(self, status=DuplicateIdCardRequest.PAID, **extra):
        return DuplicateIdCardRequest.objects.create(
            institution=self.institution, student_name="Asha Rao", class_name="7B", admission_no="A-1",
            email="asha@example.com", phone="9810044120", amount_paise=15000, status=status, **extra)

    def test_the_table_is_called_duplicate_id_card(self):
        index = self.client.get("/admin/").content.decode()
        self.assertIn(">Duplicate ID card<", index)
        self.assertNotIn("Duplicate ID card requests", index)

    def test_several_requests_are_marked_done_at_once(self):
        first, second, unpaid = self.request(), self.request(), self.request(status=DuplicateIdCardRequest.CREATED)
        response = self.client.post("/admin/idcards/duplicateidcardrequest/", {
            "action": "mark_done", "_selected_action": [first.pk, second.pk, unpaid.pk]}, follow=True)
        self.assertContains(response, "Marked 3 request(s) as done. 1 of them weren&#x27;t paid.")
        self.assertEqual(DuplicateIdCardRequest.objects.filter(handled=True).count(), 3)
        self.client.post("/admin/idcards/duplicateidcardrequest/", {
            "action": "mark_not_done", "_selected_action": [unpaid.pk]})
        unpaid.refresh_from_db()
        self.assertFalse(unpaid.handled)

    def test_guidelines_are_edited_in_the_admin_and_reach_the_page(self):
        from apps.content.models import IdCardPage

        page = self.client.get("/admin/content/idcardpage/", follow=True).content.decode()
        for field in ("guidelines_title", "guidelines_intro", "guidelines_points", "guidelines_outro",
                      "guidelines_link", "guidelines_dismiss"):
            self.assertIn(f'name="{field}"', page)
        self.client.get("/api/pages/id-card/")  # cached now
        copy = IdCardPage.load()
        copy.guidelines_title = "Read This First"
        copy.guidelines_points = "Bring the old card.\nUse capital letters."
        copy.save()
        data = self.client.get("/api/pages/id-card/").json()["copy"]
        self.assertEqual((data["guidelinesTitle"], data["guidelinesPoints"]),
                         ("Read This First", "Bring the old card.\nUse capital letters."))
