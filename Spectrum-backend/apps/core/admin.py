from django.contrib import admin, messages
from django.contrib.auth.models import Group
from django.utils import timezone

from .models import Task
from .tasks import REGISTRY

admin.site.unregister(Group)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("name", "args", "status", "attempts", "run_after", "short_error")
    list_filter = ("status", "name")
    readonly_fields = ("name", "args", "status", "attempts", "max_attempts", "run_after", "last_error", "created_at")
    actions = ["retry"]

    def has_add_permission(self, request):
        return False

    @admin.display(description="Error")
    def short_error(self, obj):
        return obj.last_error.strip().splitlines()[-1][:120] if obj.last_error else ""

    @admin.action(description="Retry selected tasks")
    def retry(self, request, queryset):
        count = queryset.filter(name__in=REGISTRY).update(
            status=Task.QUEUED, attempts=0, run_after=timezone.now())
        messages.success(request, f"Queued {count} task(s) again.")
