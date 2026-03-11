from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Workspace, Branding, UserPreferences, UserNotifications


class UserAdmin(BaseUserAdmin):
    list_display = BaseUserAdmin.list_display + ('phone',)
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Profile', {'fields': ('avatar', 'phone', 'address')}),
    )


admin.site.register(User, UserAdmin)


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'type', 'owner', 'default_template')
    raw_id_fields = ('owner', 'default_template')


admin.site.register(Branding)
admin.site.register(UserPreferences)
admin.site.register(UserNotifications)