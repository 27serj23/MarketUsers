from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("", views.index, name="index"),
    path("product/<int:id>", views.detail, name="detail"),
    path('success/', views.payment_success_view, name='success'),
    path('failed/', views.payment_failed_view, name='failed'),
    path('api/checkout-session/', views.create_checkout_session, name='api_checkout_session'),
    path('createproduct/', views.create_product, name="createproduct"),
    path('editproduct/<int:id>', views.product_edit, name="editproduct"),
    path('delete/<int:id>', views.product_delete, name="delete"),
    path('dashboard', views.dashboard, name="dashboard"),
    path('movieGallery', views.dashboard, name="movieGallery"),
    path('register', views.register, name="register"),
    path('login', auth_views.LoginView.as_view(template_name='myapp/login.html'), name="login"),
    path('logout', auth_views.LogoutView.as_view(template_name='myapp/logout.html'), name="logout"),
    path('invalid', views.invalid, name="invalid"),
    path('purchases', views.my_purchases, name="purchases"),
    path('sales', views.sales, name="sales"),
    path('cart/', views.view_cart, name='view_cart'),
    path('add_to_cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove_from_cart/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('orders', views.orders, name='orders'),
    path('search', views.search_bar, name='search'),
]