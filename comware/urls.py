"""comware URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from board import views
from django.conf.urls import url
# from accounts import views as account_views
from django.contrib.auth import views as auth_views

admin.site.site_header = 'Administración Reportes en Línea'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('enviar/<int:table_id>/', views.enviar, name='enviar'),
    # path('signup/', account_views.signup, name='signup'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('settings/password/', auth_views.PasswordChangeView.as_view(template_name='password_change.html'), name='password_change'),
    path('settings/password/done', auth_views.PasswordChangeView.as_view(template_name='password_change_done.html'), name='password_change_done'),
    path('settings/account/', views.UserUpdateView.as_view(), name='my_account'),
]
