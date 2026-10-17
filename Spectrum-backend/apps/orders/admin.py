from django.contrib import admin, messages
from django.utils.html import format_html

from apps.core.tasks import enqueue

from .models import Delivery, Order, OrderItem, Payment

STATUS_COLOURS = {"created": "#999", "paid": "#7c4de0", "failed": "#e8503a", "delivered": "#2fbf8f",
                  "refunded": "#b58900", "pending": "#b58900", "sent": "#7c4de0"}


def badge(value, label):
    return format_html('<b style="color:{}">{}</b>', STATUS_COLOURS.get(value, "#999"), label)


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class PaymentInline(ReadOnlyInline):
    model = Payment
    fields = ("razorpay_payment_id", "method", "amount_paise", "status", "verified_via", "created_at")
    readonly_fields = fields


class DeliveryInline(ReadOnlyInline):
    model = Delivery
    fields = ("channel", "status", "attempts", "last_error", "sent_at")
    readonly_fields = fields


class ItemInline(ReadOnlyInline):
    model = OrderItem
    fields = ("photo", "video", "unit_price_paise")
    readonly_fields = fields
    classes = ("collapse",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("photo", "video")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("public_id", "event", "kind", "rupees", "status_badge", "name", "phone", "email", "created_at")
    list_filter = ("status", "kind", "event")
    list_select_related = ("event",)
    search_fields = ("public_id", "name", "email", "phone", "razorpay_order_id", "payments__razorpay_payment_id")
    date_hierarchy = "created_at"
    inlines = [PaymentInline, DeliveryInline, ItemInline]
    actions = ["resend_whatsapp", "send_whatsapp_by_hand", "resend_email", "reissue_links", "refulfil"]
    readonly_fields = ("public_id", "event", "kind", "rupees", "status", "name", "email", "phone",
                       "deliver_whatsapp", "deliver_email", "razorpay_order_id", "download_link", "created_at",
                       "paid_at", "delivered_at")
    fields = readonly_fields

    def has_add_permission(self, request):
        return False

    @admin.display(description="Amount", ordering="amount_paise")
    def rupees(self, obj):
        return f"₹{obj.amount}"

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return badge(obj.status, obj.get_status_display())

    @admin.display(description="Download links")
    def download_link(self, obj):
        """Whether each one-time link has been used. Deliberately not clickable:
        opening the buyer's link here would use it up."""
        if obj.status not in (Order.PAID, Order.DELIVERED):
            return "Available after payment"
        from django.utils import timezone

        def state(used_at):
            return f"used {timezone.localtime(used_at):%d %b %Y, %H:%M}" if used_at else "not used yet"

        rows = []
        if obj.zip_file:
            rows.append(("Photos zip", state(obj.zip_used_at)))
        for item in obj.items.filter(video__isnull=False).select_related("video"):
            rows.append((item.video.title or "Event video", state(item.video_used_at)))
        if not rows:
            return "Preparing…"
        return format_html("<br>".join(["{}: {}"] * len(rows)), *[part for row in rows for part in row])

    def _resend(self, request, queryset, channel):
        count = 0
        for order in queryset.filter(status__in=[Order.PAID, Order.DELIVERED]):
            delivery, _ = Delivery.objects.get_or_create(order=order, channel=channel)
            Delivery.objects.filter(pk=delivery.pk).update(status=Delivery.PENDING, attempts=0, last_error="")
            enqueue("orders.send_delivery", delivery.pk)
            count += 1
        messages.success(request, f"Resending to {count} order(s).")

    @admin.action(description="Resend download link on WhatsApp")
    def resend_whatsapp(self, request, queryset):
        self._resend(request, queryset.exclude(phone=""), Delivery.WHATSAPP)

    @admin.action(description="Send on WhatsApp by hand (from your own phone)")
    def send_whatsapp_by_hand(self, request, queryset):
        """A page with each order's message and a wa.me button that opens the
        chat with it typed in; ticked orders are then marked sent. Opening a
        download link only shows its page, so link previews use nothing up."""
        from urllib.parse import quote

        from django.template.response import TemplateResponse

        from .jobs import mark_whatsapp_sent, whatsapp_body

        orders = list(queryset.filter(status__in=[Order.PAID, Order.DELIVERED]).exclude(phone="")
                      .select_related("event__institution"))
        if request.POST.get("confirm"):
            sent = set(request.POST.getlist("sent"))
            marked = [order for order in orders if str(order.pk) in sent]
            for order in marked:
                mark_whatsapp_sent(order, "manual")
            messages.success(request, f"Marked {len(marked)} order(s) as sent on WhatsApp.")
            return None
        if not orders:
            messages.warning(request, "None of the selected orders is paid with a WhatsApp number.")
            return None
        rows = []
        for order in orders:
            body = whatsapp_body(order)
            rows.append({"order": order, "body": body, "has_link": "/api/downloads/" in body,
                         "wa_link": f"https://wa.me/{order.phone.lstrip('+')}?text={quote(body, safe='')}",
                         "delivery": order.deliveries.filter(channel=Delivery.WHATSAPP).first()})
        return TemplateResponse(request, "admin/orders/whatsapp_by_hand.html", {
            **self.admin_site.each_context(request), "title": "Send on WhatsApp by hand", "opts": self.model._meta,
            "rows": rows, "action": "send_whatsapp_by_hand", "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
        })

    @admin.action(description="Resend download link by email")
    def resend_email(self, request, queryset):
        self._resend(request, queryset.exclude(email=""), Delivery.EMAIL)

    @admin.action(description="Issue fresh one-time links and resend them")
    def reissue_links(self, request, queryset):
        from .services import reissue_download_links

        orders = list(queryset.filter(status__in=[Order.PAID, Order.DELIVERED]))
        for order in orders:
            reissue_download_links(order)
        messages.success(request, f"New one-time links sent for {len(orders)} order(s); the old links no longer work.")

    @admin.action(description="Re-run fulfilment (items, zip, deliveries)")
    def refulfil(self, request, queryset):
        ids = list(queryset.filter(status__in=[Order.PAID, Order.DELIVERED]).values_list("pk", flat=True))
        for pk in ids:
            enqueue("orders.fulfil_order", str(pk))
        messages.success(request, f"Queued {len(ids)} order(s).")


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ("order", "channel", "status_badge", "attempts", "last_error", "sent_at")
    list_filter = ("status", "channel")
    list_select_related = ("order",)
    search_fields = ("order__public_id", "order__phone", "order__email")
    readonly_fields = ("order", "channel", "status", "attempts", "last_error", "provider_message_id", "sent_at")
    actions = ["resend"]

    def has_add_permission(self, request):
        return False

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return badge(obj.status, obj.get_status_display())

    @admin.action(description="Resend selected")
    def resend(self, request, queryset):
        ids = list(queryset.values_list("pk", flat=True))
        queryset.update(status=Delivery.PENDING, attempts=0, last_error="")
        for pk in ids:
            enqueue("orders.send_delivery", pk)
        messages.success(request, f"Resending {len(ids)} delivery(ies).")
