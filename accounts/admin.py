from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Organization, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'org_type', 'phone', 'is_verified', 'created_at')
    list_filter = ('org_type', 'is_verified')
    search_fields = ('name', 'phone', 'address')


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
