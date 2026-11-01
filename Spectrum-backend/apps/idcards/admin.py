import os

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse
from django.urls import path, reverse
from django.utils import timezone

from apps.core.models import delete_files
from apps.core.tasks import enqueue
from apps.core.xlsx import workbook_bytes
from apps.orders.admin import badge
from spectrum.storages import private_storage

from .models import DuplicateIdCardRequest


class _ReceiptLink:
    """What the upload field shows as "Currently": the receipt's name, linked
    to the admin's own download (the file itself is private)."""

    def __init__(self, file):
        self.url = reverse("admin:idcards_duplicateidcardrequest_receipt", args=[file.instance.pk])
        self.name = os.path.basename(file.name)

    def __str__(self):
        return self.name


class ReceiptInput(forms.ClearableFileInput):
    def format_value(self, value):
        value = super().format_value(value)
        return _ReceiptLink(value) if self.is_initial(value) else value


@admin.register(DuplicateIdCardRequest)
class DuplicateIdCardRequestAdmin(admin.ModelAdmin):
    """Every request made on the website's ID Card page. Only paid ones need a
    card; uploading its shipment receipt marks it Shipped and emails it."""

    list_display = ("public_id", "student_name", "class_name", "admission_no", "card_type", "lanyard_colour",
                    "institution", "rupees", "status_badge", "email", "phone", "created_at", "shipment_receipt",
                    "receipt_emailed_at", "handled")
    list_display_links = ("public_id", "student_name")
    list_editable = ("shipment_receipt", "handled")
    list_filter = ("status", "handled", "institution", "card_type", "lanyard_colour")
    list_select_related = ("institution",)
    search_fields = ("public_id", "student_name", "admission_no", "class_name", "email", "phone",
                     "institution__name", "razorpay_order_id", "razorpay_payment_id")
    date_hierarchy = "created_at"
    readonly_fields = ("public_id", "student_name", "class_name", "admission_no", "card_type", "lanyard_colour",
                       "institution", "email", "phone",
                       "rupees", "status", "razorpay_order_id", "razorpay_payment_id", "paid_via", "created_at",
                       "paid_at", "shipped_at", "receipt_emailed_at")
    fields = (*readonly_fields, "shipment_receipt", "handled")
    formfield_overrides = {DuplicateIdCardRequest._meta.get_field("shipment_receipt").__class__: {
        "widget": ReceiptInput}}
    actions = ["export_selected", "mark_done", "mark_not_done", "resend_receipt"]
    # Adds the "Export selected" button above the filters.
    change_list_template = "admin/idcards/duplicateidcardrequest/change_list.html"

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        receipt = path("<path:object_id>/receipt/", self.admin_site.admin_view(self.receipt_view),
                       name="idcards_duplicateidcardrequest_receipt")
        return [receipt, *super().get_urls()]

    def receipt_view(self, request, object_id):
        from apps.orders.views import _serve_private

        if not self.has_view_permission(request):
            raise PermissionDenied
        card = DuplicateIdCardRequest.objects.filter(pk=object_id).exclude(shipment_receipt="").first()
        if card is None:
            raise Http404("No shipment receipt")
        name = card.shipment_receipt.name
        return _serve_private(name, f"shipment-receipt-{card.public_id}{os.path.splitext(name)[1]}")

    def save_model(self, request, obj, form, change):
        """A new receipt ships the request (and marks it done) and emails the
        receipt; a removed one puts the request back to Paid. Works from the
        table and from the request's own page."""
        if "shipment_receipt" not in form.changed_data:
            return super().save_model(request, obj, form, change)
        previous = (DuplicateIdCardRequest.objects.filter(pk=obj.pk)
                    .values_list("shipment_receipt", flat=True).first() or "")
        if obj.shipment_receipt:
            obj.status, obj.handled = DuplicateIdCardRequest.SHIPPED, True
            obj.shipped_at, obj.receipt_emailed_at = timezone.now(), None
        else:
            obj.status, obj.shipped_at, obj.receipt_emailed_at = DuplicateIdCardRequest.PAID, None, None
        super().save_model(request, obj, form, change)
        if previous and previous != obj.shipment_receipt.name:
            transaction.on_commit(lambda: delete_files(private_storage(), [previous]))
        if obj.shipment_receipt:
            enqueue("idcards.email_receipt", str(obj.pk))
            messages.success(request, f"{obj.public_id} is shipped; the receipt is being emailed to {obj.email}.")

    @admin.action(description="Export selected requests to Excel")
    def export_selected(self, request, queryset):
        """Every ticked request (or, with "select all", every one matching the
        filters), oldest first: the date it was made and everything the form asked for."""
        rows = [("Request no.", "Date of request", "Name", "Class", "Admission No.", "Type of card",
                 "Color of Lanyard", "School Name/Branch", "Email", "Phone Number", "Status")]
        for card in queryset.select_related("institution").order_by("created_at"):
            rows.append((card.public_id, timezone.localtime(card.created_at).strftime("%d %b %Y, %H:%M"),
                         card.student_name, card.class_name, card.admission_no, card.card_type,
                         card.lanyard_colour, card.institution.name, card.email, card.phone,
                         card.get_status_display()))
        content = workbook_bytes(rows, widths=(14, 19, 26, 10, 16, 14, 17, 34, 30, 16, 16),
                                 sheet_name="Duplicate ID cards")
        response = HttpResponse(
            content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = (
            f'attachment; filename="duplicate-id-cards-{timezone.localdate():%Y-%m-%d}.xlsx"')
        return response

    @admin.action(description="Mark selected requests as done")
    def mark_done(self, request, queryset):
        unpaid = queryset.exclude(status__in=DuplicateIdCardRequest.PAID_STATES).count()
        count = queryset.filter(handled=False).update(handled=True)
        note = f" {unpaid} of them weren't paid." if unpaid else ""
        messages.success(request, f"Marked {count} request(s) as done.{note}")

    @admin.action(description="Mark selected requests as not done")
    def mark_not_done(self, request, queryset):
        count = queryset.filter(handled=True).update(handled=False)
        messages.success(request, f"Marked {count} request(s) as not done.")

    @admin.action(description="Email the shipment receipt again")
    def resend_receipt(self, request, queryset):
        ids = [str(pk) for pk in queryset.exclude(shipment_receipt="").values_list("pk", flat=True)]
        for pk in ids:
            enqueue("idcards.email_receipt", pk)
        skipped = queryset.count() - len(ids)
        note = f" {skipped} had no receipt." if skipped else ""
        messages.success(request, f"Emailing the receipt again for {len(ids)} request(s).{note}")

    @admin.display(description="Amount", ordering="amount_paise")
    def rupees(self, obj):
        return f"₹{obj.amount}"

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return badge(obj.status, obj.get_status_display())
