from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('user/', views.customer_dashboard, name='customer_dashboard'),
    path('bill/', views.bill_generation, name='bill_generation'),
    path('request-delete/', views.request_delete, name='request_delete'),
    path('delete-user/<str:username>/', views.delete_user, name='delete_user'),
    path('logout/', views.logout_view, name='logout'),
    path('approve-registration/<int:request_id>/', views.approve_registration, name='approve_registration'),
    path('approve-delete/<str:username>/', views.approve_delete, name='approve_delete'),
    path('reject-request/<int:request_id>/', views.reject_request, name='reject_request'),
    path('update-tables/', views.update_tables, name='update_tables'),
    path('update_profile/', views.update_profile, name='update_profile'),

]
