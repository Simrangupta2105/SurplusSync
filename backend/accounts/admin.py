from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Organization, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'org_type', 'business_segment', 'promotion_active', 'phone', 'is_verified', 'created_at')
    list_filter = ('org_type', 'business_segment', 'promotion_active', 'is_verified')
    list_editable = ('is_verified', 'promotion_active')
    search_fields = ('name', 'phone', 'address')
    actions = ['approve_organizations', 'revoke_verification']

    @admin.action(description="Approve selected NGOs / Organizations")
    def approve_organizations(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f"Successfully approved {updated} organization(s).")

    @admin.action(description="Revoke verification for selected Organizations")
    def revoke_verification(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f"Successfully revoked verification for {updated} organization(s).")


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'organization', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active', 'organization')
    fieldsets = UserAdmin.fieldsets + (
        ('Organization Info', {'fields': ('organization', 'role')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Organization Info', {'fields': ('organization', 'role')}),
    )
