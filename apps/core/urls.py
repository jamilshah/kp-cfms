"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: URL routing for core app (notifications, bank accounts).
-------------------------------------------------------------------------
"""
from django.urls import path
from apps.core.views import (
    NotificationListView,
    notification_dropdown_view,
    notification_badge_view,
    notification_mark_read_view,
    notification_mark_all_read_view,
)

app_name = 'core'

urlpatterns = [
    # Notification URLs
    path('notifications/', NotificationListView.as_view(), name='notification_list'),
    path('notifications/dropdown/', notification_dropdown_view, name='notification_dropdown'),
    path('notifications/badge/', notification_badge_view, name='notification_badge'),
    path('notifications/<int:pk>/mark-read/', notification_mark_read_view, name='notification_mark_read'),
    path('notifications/mark-all-read/', notification_mark_all_read_view, name='notification_mark_all_read'),
]
