from django.contrib import admin
from .models import Portfolio, PortfolioImage, Proposal, Template


class PortfolioImageInline(admin.TabularInline):
    model = PortfolioImage
    extra = 0
    max_num = 10


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ('title', 'source', 'workspace', 'user', 'created_at')
    list_filter = ('source', 'workspace')
    search_fields = ('title',)
    raw_id_fields = ('workspace', 'user')
    readonly_fields = ('id', 'fetch_date', 'created_at', 'updated_at')
    inlines = [PortfolioImageInline]


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'active')
    list_filter = ('category', 'active')
    search_fields = ('title',)


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'sentvia', 'genby', 'company_name', 'category', 'client', 'workspace', 'total', 'created_at')
    list_filter = ('status',)
    search_fields = ('title',)
    raw_id_fields = ('client', 'sender', 'workspace')
    readonly_fields = ('id', 'created_at', 'updated_at')
    filter_horizontal = ('projects',)
