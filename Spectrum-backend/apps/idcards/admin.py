from django.contrib import admin

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

    def has_add_permission(self, request):
        return False

    @admin.display(description="Amount", ordering="amount_paise")
    def rupees(self, obj):
        return f"₹{obj.amount}"

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return badge(obj.status, obj.get_status_display())
