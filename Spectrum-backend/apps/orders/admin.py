from django.conf import settings
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
    actions = ["resend_whatsapp", "resend_email", "refulfil"]
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

    @admin.display(description="Customer download page")
    def download_link(self, obj):
        if obj.status not in (Order.PAID, Order.DELIVERED):
            return "Available after payment"
        url = f"{settings.SITE_URL}/downloads/{obj.download_token}"
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', url, url)

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

    @admin.action(description="Resend download link by email")
    def resend_email(self, request, queryset):
        self._resend(request, queryset.exclude(email=""), Delivery.EMAIL)

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
