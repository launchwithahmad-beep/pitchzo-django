from django.contrib import admin
from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'type', 'workspace', 'phone', 'address')
    list_filter = ('type', 'workspace')
    search_fields = ('name', 'email')
    list_display_links = ('name', 'email')
    raw_id_fields = ('workspace',)
    readonly_fields = ('id',)
