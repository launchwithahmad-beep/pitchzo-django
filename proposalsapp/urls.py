from django.urls import path
from . import views

urlpatterns = [
    path('templates/', views.template_list_create, name='template_list_create'),
    path('templates/<int:template_id>/', views.template_detail, name='template_detail'),
    path('workspaces/by-slug/<slug:slug>/portfolios/', views.portfolio_list_create, name='portfolio_list_create'),
    path('workspaces/by-slug/<slug:slug>/portfolios/<uuid:portfolio_id>/', views.portfolio_detail, name='portfolio_detail'),
    path('workspaces/by-slug/<slug:slug>/proposals/', views.proposal_list_create, name='proposal_list_create'),
    path('workspaces/by-slug/<slug:slug>/proposals/<uuid:proposal_id>/', views.proposal_detail, name='proposal_detail'),
]
