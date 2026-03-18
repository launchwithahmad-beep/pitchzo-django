from django.urls import path
from . import views

urlpatterns = [
    path('templates/', views.template_list_create, name='template_list_create'),
    path('workspaces/by-slug/<slug:slug>/overview/', views.workspace_overview, name='workspace_overview'),
    path('templates/<int:template_id>/', views.template_detail, name='template_detail'),
    path('workspaces/by-slug/<slug:slug>/portfolios/', views.portfolio_list_create, name='portfolio_list_create'),
    path('workspaces/by-slug/<slug:slug>/portfolios/<uuid:portfolio_id>/', views.portfolio_detail, name='portfolio_detail'),
    path('workspaces/by-slug/<slug:slug>/proposals/', views.proposal_list_create, name='proposal_list_create'),
    path('workspaces/by-slug/<slug:slug>/clients/<uuid:client_id>/proposals/', views.client_proposals_list, name='client_proposals_list'),
    path('workspaces/by-slug/<slug:slug>/proposals/<uuid:proposal_id>/', views.proposal_detail, name='proposal_detail'),
    path('workspaces/by-slug/<slug:slug>/proposals/<uuid:proposal_id>/preview/', views.proposal_preview, name='proposal_preview'),
    path('workspaces/by-slug/<slug:slug>/proposals/<uuid:proposal_id>/builder-snapshot/', views.proposal_builder_snapshot, name='proposal_builder_snapshot'),
    path('workspaces/by-slug/<slug:slug>/proposals/<uuid:proposal_id>/sections/reorder/', views.proposal_section_reorder, name='proposal_section_reorder'),
    path('workspaces/by-slug/<slug:slug>/proposals/<uuid:proposal_id>/sections/<uuid:section_id>/media/', views.proposal_section_media_upload, name='proposal_section_media_upload'),
    path('workspaces/by-slug/<slug:slug>/proposals/<uuid:proposal_id>/sections/<uuid:section_id>/', views.proposal_section_detail, name='proposal_section_detail'),
    path('workspaces/by-slug/<slug:slug>/proposals/<uuid:proposal_id>/sections/', views.proposal_section_list_create, name='proposal_section_list_create'),
]
