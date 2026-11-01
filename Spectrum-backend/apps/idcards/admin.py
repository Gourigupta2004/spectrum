from django.contrib import admin, messages

from apps.orders.admin import badge

from .models import DuplicateIdCardRequest


@admin.register(DuplicateIdCardRequest)
class DuplicateIdCardRequestAdmin(admin.ModelAdmin):
    """Every request made on the website's ID Card page. Only paid ones need a
    card; tick Done once it has been made."""

    list_display = ("public_id", "student_name", "class_name", "admission_no", "institution", "rupees",
                    "status_badge", "email", "phone", "created_at", "handled")
    list_display_links = ("public_id", "student_name")
    list_editable = ("handled",)
    list_filter = ("status", "handled", "institution")
    list_select_related = ("institution",)
    search_fields = ("public_id", "student_name", "admission_no", "class_name", "email", "phone",
                     "institution__name", "razorpay_order_id", "razorpay_payment_id")
    date_hierarchy = "created_at"
    readonly_fields = ("public_id", "student_name", "class_name", "admission_no", "institution", "email", "phone",
                       "rupees", "status", "razorpay_order_id", "razorpay_payment_id", "paid_via", "created_at",
                       "paid_at")
    fields = (*readonly_fields, "handled")
    actions = ["mark_done", "mark_not_done"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Mark selected requests as done")
    def mark_done(self, request, queryset):
        unpaid = queryset.exclude(status=DuplicateIdCardRequest.PAID).count()
        count = queryset.filter(handled=False).update(handled=True)
        note = f" {unpaid} of them weren't paid." if unpaid else ""
        messages.success(request, f"Marked {count} request(s) as done.{note}")

    @admin.action(description="Mark selected requests as not done")
    def mark_not_done(self, request, queryset):
        count = queryset.filter(handled=True).update(handled=False)
        messages.success(request, f"Marked {count} request(s) as not done.")

    @admin.display(description="Amount", ordering="amount_paise")
    def rupees(self, obj):
        return f"₹{obj.amount}"

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return badge(obj.status, obj.get_status_display())
