from django.contrib import admin
from .models import AdminAuditLog


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "admin_user", "action", "target_type", "target_id")
    list_filter = ("action", "target_type", "created_at")
    search_fields = ("action", "target_type", "target_id", "admin_user__username")
    readonly_fields = ("admin_user", "action", "target_type", "target_id", "details", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


from .models import Issue


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "status", "priority", "reporter", "reporter_org", "target_org", "created_at")
    list_filter = ("status", "priority", "category", "created_at")
    search_fields = ("description", "admin_notes", "reporter__username", "reporter_org__name", "target_org__name")
    readonly_fields = ("created_at", "updated_at")

