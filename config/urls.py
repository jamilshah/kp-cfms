"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
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
from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views
from apps.users.forms import CNICAuthenticationForm

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(authentication_form=CNICAuthenticationForm), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Override the default accounts login to use CNIC-normalizing form
    path('accounts/login/', auth_views.LoginView.as_view(authentication_form=CNICAuthenticationForm), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('core/', include('apps.core.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('budgeting/', include('apps.budgeting.urls')),
    path('expenditure/', include('apps.expenditure.urls')),
    path('revenue/', include('apps.revenue.urls')),
    path('finance/', include('apps.finance.urls')),
    path('reports/', include('apps.reporting.urls')),
    path('system-admin/', include('apps.system_admin.urls')),
    path('', RedirectView.as_view(url='/dashboard/', permanent=False), name='home'),
]

