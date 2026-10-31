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
    # The institution is the event's: shown and filtered through it, nothing stored on the order.
    list_display = ("public_id", "institution", "event", "kind", "rupees", "status_badge", "name", "phone", "email",
                    "created_at")
    list_filter = ("status", "kind", "event__institution", "event")
    list_select_related = ("event__institution",)
    search_fields = ("public_id", "name", "email", "phone", "razorpay_order_id", "payments__razorpay_payment_id",
                     "event__institution__name", "event__name")
    date_hierarchy = "created_at"
    inlines = [PaymentInline, DeliveryInline, ItemInline]
    actions = ["send_whatsapp_by_hand", "send_email_by_hand", "mark_delivered", "resend_whatsapp", "resend_email",
               "reissue_links", "refulfil"]
    readonly_fields = ("public_id", "institution", "event", "kind", "rupees", "status", "name", "email", "phone",
                       "deliver_whatsapp", "deliver_email", "razorpay_order_id", "download_link", "created_at",
                       "paid_at", "delivered_at")
    fields = readonly_fields

    def has_add_permission(self, request):
        return False

    @admin.display(description="Institution", ordering="event__institution__name")
    def institution(self, obj):
        return obj.event.institution

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

    def _by_hand(self, request, queryset, channel):
        """A page with each order's message and buttons that open it ready to
        send from staff's own WhatsApp or mailbox; ticked orders are then marked
        sent. Opening a download link only shows its page, so link previews and
        mail scanners use nothing up."""
        from urllib.parse import quote, urlencode

        from django.template.response import TemplateResponse

        from .jobs import email_body, email_subject, mark_sent, whatsapp_body

        whatsapp = channel == Delivery.WHATSAPP
        contact = "phone" if whatsapp else "email"
        label = "WhatsApp" if whatsapp else "email"
        orders = list(queryset.filter(status__in=[Order.PAID, Order.DELIVERED]).exclude(**{contact: ""})
                      .select_related("event__institution"))
        if request.POST.get("confirm"):
            sent = set(request.POST.getlist("sent"))
            marked = [order for order in orders if str(order.pk) in sent]
            for order in marked:
                mark_sent(order, channel, "manual")
            messages.success(request, f"Marked {len(marked)} order(s) as sent by {label}.")
            return None
        if not orders:
            messages.warning(request, f"None of the selected orders is paid with {'a WhatsApp number' if whatsapp else 'an email address'}.")
            return None
        rows = []
        for order in orders:
            if whatsapp:
                body, subject = whatsapp_body(order), ""
                phone, text = order.phone.lstrip("+"), quote(body, safe="")
                buttons = [("Open in WhatsApp Web", f"https://web.whatsapp.com/send?phone={phone}&text={text}"),
                           ("Open in WhatsApp app", f"https://wa.me/{phone}?text={text}")]
            else:
                body, subject = email_body(order), email_subject(order)
                buttons = [("Open in Gmail", "https://mail.google.com/mail/?" + urlencode(
                               {"view": "cm", "fs": "1", "to": order.email, "su": subject, "body": body}, quote_via=quote)),
                           ("Open in mail app", f"mailto:{quote(order.email, safe='@')}?"
                                                + urlencode({"subject": subject, "body": body}, quote_via=quote))]
            rows.append({"order": order, "to": getattr(order, contact), "subject": subject, "body": body,
                         "buttons": buttons, "has_link": "/api/downloads/" in body,
                         "delivery": order.deliveries.filter(channel=channel).first()})
        return TemplateResponse(request, "admin/orders/send_by_hand.html", {
            **self.admin_site.each_context(request), "title": f"Send by {label} by hand", "opts": self.model._meta,
            "rows": rows, "label": label, "action": f"send_{channel}_by_hand",
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
        })

    @admin.action(description="Send on WhatsApp by hand (from your own WhatsApp)")
    def send_whatsapp_by_hand(self, request, queryset):
        return self._by_hand(request, queryset, Delivery.WHATSAPP)

    @admin.action(description="Send by email by hand (from your own mailbox)")
    def send_email_by_hand(self, request, queryset):
        return self._by_hand(request, queryset, Delivery.EMAIL)

    @admin.action(description="Mark as delivered (links sent some other way)")
    def mark_delivered(self, request, queryset):
        """Closes paid orders: any delivery not yet out is recorded as sent by
        hand, so the worker never sends it again and it leaves the failed queue."""
        from django.utils import timezone

        from .jobs import mark_sent

        orders = list(queryset.filter(status=Order.PAID))
        for order in orders:
            for channel in order.deliveries.exclude(status__in=[Delivery.SENT, Delivery.DELIVERED]).values_list(
                    "channel", flat=True):
                mark_sent(order, channel, "manual")
            Order.objects.filter(pk=order.pk, status=Order.PAID).update(status=Order.DELIVERED,
                                                                         delivered_at=timezone.now())
        messages.success(request, f"Marked {len(orders)} order(s) as delivered.")

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
