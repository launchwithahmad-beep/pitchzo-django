from django.urls import path
from . import views

urlpatterns = [
    path('workspaces/by-slug/<slug:slug>/clients/', views.client_list_create, name='client_list_create'),
    path('workspaces/by-slug/<slug:slug>/clients/<uuid:client_id>/', views.client_detail, name='client_detail'),
]
