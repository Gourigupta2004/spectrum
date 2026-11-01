import hashlib
import hmac
import json
from unittest import mock

from django.core.exceptions import ValidationError

from apps.idcards.models import DuplicateIdCardRequest

from .base import SpectrumTestCase


def sign(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


class IdCardRequestCase(SpectrumTestCase):
    """An institution offering duplicate ID cards, and a way to request one."""

    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.institution.offers_duplicate_id_cards = True
        self.institution.duplicate_id_card_price = 150
        self.institution.save()

    def create(self, **overrides):
        body = {"institutionId": "dps", "studentName": "Asha Rao", "className": "7B", "admissionNo": "A-1042",
                "cardType": "Student", "lanyardColour": "Blue", "email": "asha@example.com", "phone": "98100 44120",
                "idempotencyKey": "key-1-aaaaaaaaaaaaaaaa", **overrides}
        ids = iter(f"order_ID{i}" for i in range(DuplicateIdCardRequest.objects.count() + 1, 100))
        with mock.patch("apps.idcards.views.razorpay_create_order", side_effect=lambda card: next(ids)):
            return self.client.post("/api/idcards/duplicate/", json.dumps(body), content_type="application/json")


class DuplicateIdCardTests(IdCardRequestCase):
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
        self.assertEqual(self.create(email="").json()["field"], "email")  # the shipment receipt is emailed
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


class CardTypeAndLanyardTests(IdCardRequestCase):
    """Type of card and Color of Lanyard: dropdowns whose choices are edited on the ID card page in the admin."""

    def test_the_page_lists_the_choices_from_the_admin(self):
        data = self.client.get("/api/pages/id-card/").json()
        self.assertEqual(data["cardTypes"], ["Student", "Parent"])
        self.assertEqual(data["lanyardColours"], ["Blue", "Red", "Yellow", "Green"])
        self.assertEqual((data["copy"]["cardTypePlaceholder"], data["copy"]["lanyardPlaceholder"]),
                         ("Type of card", "Color of Lanyard"))
        from apps.content.models import LanyardColour

        LanyardColour.objects.create(label="Black", sort_order=9)
        self.assertEqual(self.client.get("/api/pages/id-card/").json()["lanyardColours"][-1], "Black")

    def test_the_choices_are_kept_on_the_request_and_must_be_real(self):
        self.assertEqual(self.create(cardType="Teacher").json()["field"], "cardType")
        self.assertEqual(self.create(lanyardColour="").json()["field"], "lanyardColour")
        self.assertEqual(self.create(cardType="Parent", lanyardColour="Green").status_code, 200)
        card = DuplicateIdCardRequest.objects.get()
        self.assertEqual((card.card_type, card.lanyard_colour), ("Parent", "Green"))
        self.client.force_login(self.make_staff())
        html = self.client.get("/admin/idcards/duplicateidcardrequest/").content.decode()
        self.assertIn("Parent", html)
        self.assertIn("Green", html)

    def test_a_dropdown_without_choices_is_not_asked_for(self):
        from apps.content.models import IdCardType

        IdCardType.objects.all().delete()
        self.assertEqual(self.create(cardType="").status_code, 200)
        self.assertEqual(DuplicateIdCardRequest.objects.get().card_type, "")


class ShipmentReceiptTests(SpectrumTestCase):
    """Uploading a paid request's shipment receipt marks it Shipped and emails the receipt."""

    URL = "/admin/idcards/duplicateidcardrequest/"

    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.client.force_login(self.make_staff())
        self.card = DuplicateIdCardRequest.objects.create(
            institution=self.institution, student_name="Asha Rao", class_name="7B", admission_no="A-1",
            email="asha@example.com", phone="9810044120", amount_paise=15000, status=DuplicateIdCardRequest.PAID,
            razorpay_order_id="order_ID1")

    def receipt(self, name="receipt.pdf", body=b"%PDF-1.4 receipt"):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(name, body, content_type="application/pdf")

    def upload_on_page(self, **data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(f"{self.URL}{self.card.pk}/change/", {"_save": "Save", **data}, follow=True)

    def test_uploading_the_receipt_ships_the_request_and_emails_it(self):
        from django.core import mail

        response = self.upload_on_page(shipment_receipt=self.receipt())
        self.assertContains(response, "is shipped; the receipt is being emailed to asha@example.com")
        self.card.refresh_from_db()
        self.assertEqual(self.card.status, DuplicateIdCardRequest.SHIPPED)
        self.assertTrue(self.card.handled)
        self.assertIsNotNone(self.card.shipped_at)
        self.assertIsNotNone(self.card.receipt_emailed_at)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["asha@example.com"])
        self.assertIn(self.card.public_id, message.subject)
        self.assertIn("Asha Rao", message.body)
        filename, content, mimetype = message.attachments[0]
        self.assertEqual((filename, content, mimetype),
                         (f"shipment-receipt-{self.card.public_id}.pdf", b"%PDF-1.4 receipt", "application/pdf"))

    def test_uploading_from_the_table_works_too(self):
        from django.core import mail

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.URL, {
                "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1", "form-0-id": str(self.card.pk),
                "form-0-shipment_receipt": self.receipt("receipt.jpg", b"jpeg"), "_save": "Save"})
        self.card.refresh_from_db()
        self.assertEqual(self.card.status, DuplicateIdCardRequest.SHIPPED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertContains(self.client.get(self.URL), "Shipped")

    def test_staff_open_the_receipt_through_the_admin(self):
        self.upload_on_page(shipment_receipt=self.receipt())
        page = self.client.get(f"{self.URL}{self.card.pk}/change/").content.decode()
        link = f"{self.URL}{self.card.pk}/receipt/"
        self.assertIn(f'href="{link}"', page)
        response = self.client.get(link)
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4 receipt")
        self.client.logout()
        self.assertEqual(self.client.get(link).status_code, 302)  # to the admin sign-in

    def test_unpaid_requests_and_other_file_types_are_refused(self):
        self.card.status = DuplicateIdCardRequest.CREATED
        self.card.save()
        self.assertContains(self.upload_on_page(shipment_receipt=self.receipt()), "Only a paid request can be shipped")
        self.card.status = DuplicateIdCardRequest.PAID
        self.card.save()
        self.assertContains(self.upload_on_page(shipment_receipt=self.receipt("receipt.exe")), "PDF, JPG, PNG or WebP")
        self.card.refresh_from_db()
        self.assertEqual((self.card.status, self.card.shipment_receipt.name), (DuplicateIdCardRequest.PAID, ""))

    def test_removing_the_receipt_puts_the_request_back_to_paid(self):
        self.upload_on_page(shipment_receipt=self.receipt())
        self.upload_on_page(**{"shipment_receipt-clear": "on", "handled": "on"})
        self.card.refresh_from_db()
        self.assertEqual((self.card.status, self.card.shipped_at), (DuplicateIdCardRequest.PAID, None))

    def test_a_late_payment_webhook_never_undoes_shipped(self):
        from apps.idcards.services import mark_paid

        self.upload_on_page(shipment_receipt=self.receipt())
        mark_paid(self.card.pk, "pay_late", via="webhook")
        self.card.refresh_from_db()
        self.assertEqual(self.card.status, DuplicateIdCardRequest.SHIPPED)

    def test_the_receipt_can_be_emailed_again(self):
        from django.core import mail

        self.upload_on_page(shipment_receipt=self.receipt())
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.URL, {"action": "resend_receipt", "_selected_action": [self.card.pk]})
        self.assertEqual(len(mail.outbox), 2)


class ExportTests(SpectrumTestCase):
    URL = "/admin/idcards/duplicateidcardrequest/"

    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.client.force_login(self.make_staff())

    def request(self, name, **extra):
        return DuplicateIdCardRequest.objects.create(
            institution=self.institution, student_name=name, class_name="7B", admission_no=f"A-{name}",
            card_type="Parent", lanyard_colour="Green", email="asha@example.com", phone="+919810044120",
            amount_paise=15000, status=DuplicateIdCardRequest.PAID, **extra)

    def sheet(self, response) -> str:
        import zipfile
        from io import BytesIO

        self.assertIn("spreadsheetml.sheet", response["Content-Type"])
        self.assertIn("duplicate-id-cards-", response["Content-Disposition"])
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            return archive.read("xl/worksheets/sheet1.xml").decode()

    def test_the_button_sits_above_the_filters(self):
        self.request("Asha")
        html = self.client.get(self.URL).content.decode()
        self.assertIn('id="export-selected"', html)
        self.assertLess(html.index('id="export-selected"'), html.index('id="changelist-filter"'))
        self.assertIn('value="export_selected"', html)

    def test_only_the_ticked_requests_are_exported_with_every_form_field(self):
        asha, ravi, left_out = self.request("Asha"), self.request("Ravi"), self.request("Meera")
        response = self.client.post(self.URL, {"action": "export_selected", "index": "0",
                                               "_selected_action": [asha.pk, ravi.pk]})
        sheet = self.sheet(response)
        for heading in ("Request no.", "Date of request", "Name", "Class", "Admission No.", "Type of card",
                        "Color of Lanyard", "School Name/Branch", "Email", "Phone Number"):
            self.assertIn(f">{heading}<", sheet)
        for value in (asha.public_id, "A-Asha", "A-Ravi", "7B", "Parent", "Green", "Delhi Public School",
                      "asha@example.com", "+919810044120", "Paid"):
            self.assertIn(value, sheet)
        self.assertNotIn("Meera", sheet)
        self.assertNotIn(left_out.public_id, sheet)

    def test_nothing_ticked_exports_nothing(self):
        self.request("Asha")
        response = self.client.post(self.URL, {"action": "export_selected", "index": "0"}, follow=True)
        self.assertNotIn("Content-Disposition", response)
        self.assertContains(response, "Items must be selected")
