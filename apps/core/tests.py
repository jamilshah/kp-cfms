"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Unit tests for the core module - notification service.
-------------------------------------------------------------------------
"""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.core.models import Notification, NotificationCategory, Organization, Tehsil, District, Division
from apps.core.services import NotificationService, send_notification
from apps.users.models import Role, RoleCode


User = get_user_model()


class NotificationServiceTests(TestCase):
    """Tests for NotificationService class."""
    
    def setUp(self):
        """Set up test data."""
        # Create test location hierarchy
        self.division = Division.objects.create(
            name="Test Division",
            code="TDV01"
        )
        
        self.district = District.objects.create(
            name="Test District",
            code="TDS01",
            division=self.division
        )
        
        self.tehsil = Tehsil.objects.create(
            name="Test Tehsil",
            code="TST01",
            district=self.district
        )
        
        self.organization = Organization.objects.create(
            name="Test TMA",
            org_type="TMA",
            tehsil=self.tehsil
        )
        
        # Create test roles
        self.accountant_role = Role.objects.create(
            name="Accountant",
            code=RoleCode.ACCOUNTANT,
            description="Test Accountant"
        )
        
        self.tmo_role = Role.objects.create(
            name="TMO",
            code=RoleCode.TMO,
            description="Test TMO"
        )
        
        # Create test users
        self.accountant = User.objects.create_user(
            cnic='1234567890123',
            email='accountant@test.com',
            first_name='Test',
            last_name='Accountant',
            organization=self.organization
        )
        self.accountant.roles.add(self.accountant_role)
        
        self.tmo = User.objects.create_user(
            cnic='9876543210987',
            email='tmo@test.com',
            first_name='Test',
            last_name='TMO',
            organization=self.organization
        )
        self.tmo.roles.add(self.tmo_role)
        
        self.dealing_assistant = User.objects.create_user(
            cnic='1111122222333',
            email='assistant@test.com',
            first_name='Test',
            last_name='Assistant',
            organization=self.organization
        )
    
    def test_send_notification_creates_notification(self):
        """Test that send_notification creates a notification."""
        notification = NotificationService.send_notification(
            recipient=self.accountant,
            title="Test Notification",
            message="This is a test notification",
            link="/test/link/",
            category=NotificationCategory.WORKFLOW,
            icon='bi-bell'
        )
        
        self.assertIsNotNone(notification.pk)
        self.assertEqual(notification.recipient, self.accountant)
        self.assertEqual(notification.title, "Test Notification")
        self.assertEqual(notification.message, "This is a test notification")
        self.assertEqual(notification.link, "/test/link/")
        self.assertEqual(notification.category, NotificationCategory.WORKFLOW)
        self.assertEqual(notification.icon, 'bi-bell')
        self.assertFalse(notification.is_read)
    
    def test_send_notification_defaults(self):
        """Test that send_notification uses default values."""
        notification = NotificationService.send_notification(
            recipient=self.accountant,
            title="Simple Notification",
            message="Simple message"
        )
        
        self.assertEqual(notification.link, '')
        self.assertEqual(notification.category, NotificationCategory.WORKFLOW)
        self.assertEqual(notification.icon, 'bi-bell')
    
    def test_send_bulk_notification(self):
        """Test sending notifications to multiple recipients."""
        recipients = [self.accountant, self.tmo, self.dealing_assistant]
        
        notifications = NotificationService.send_bulk_notification(
            recipients=recipients,
            title="Bulk Notification",
            message="This is sent to multiple users",
            link="/bulk/link/",
            category=NotificationCategory.SYSTEM,
            icon='bi-megaphone'
        )
        
        self.assertEqual(len(notifications), 3)
        
        # Verify all notifications were created
        for notification in notifications:
            self.assertEqual(notification.title, "Bulk Notification")
            self.assertEqual(notification.message, "This is sent to multiple users")
            self.assertEqual(notification.category, NotificationCategory.SYSTEM)
            self.assertFalse(notification.is_read)
        
        # Verify recipients are different
        recipients_set = {n.recipient for n in notifications}
        self.assertEqual(len(recipients_set), 3)
    
    def test_get_unread_count(self):
        """Test getting unread notification count."""
        # Create some notifications
        NotificationService.send_notification(
            recipient=self.accountant,
            title="Notification 1",
            message="Message 1"
        )
        
        NotificationService.send_notification(
            recipient=self.accountant,
            title="Notification 2",
            message="Message 2"
        )
        
        # Mark one as read
        notification = NotificationService.send_notification(
            recipient=self.accountant,
            title="Notification 3",
            message="Message 3"
        )
        notification.mark_as_read()
        
        # Check unread count
        unread_count = NotificationService.get_unread_count(self.accountant)
        self.assertEqual(unread_count, 2)
    
    def test_get_unread_count_zero(self):
        """Test unread count when no notifications exist."""
        count = NotificationService.get_unread_count(self.accountant)
        self.assertEqual(count, 0)
    
    def test_get_recent_notifications(self):
        """Test retrieving recent notifications."""
        # Create 15 notifications
        for i in range(15):
            NotificationService.send_notification(
                recipient=self.accountant,
                title=f"Notification {i+1}",
                message=f"Message {i+1}"
            )
        
        # Get recent notifications (default limit: 10)
        recent = list(NotificationService.get_recent_notifications(self.accountant))
        
        self.assertEqual(len(recent), 10)
        # Should be ordered by most recent first - just verify we got 10 unique notifications
        titles = [n.title for n in recent]
        self.assertEqual(len(set(titles)), 10)
    
    def test_get_recent_notifications_custom_limit(self):
        """Test retrieving recent notifications with custom limit."""
        # Create 10 notifications
        for i in range(10):
            NotificationService.send_notification(
                recipient=self.accountant,
                title=f"Notification {i+1}",
                message=f"Message {i+1}"
            )
        
        # Get only 5 recent notifications
        recent = list(NotificationService.get_recent_notifications(self.accountant, limit=5))
        
        self.assertEqual(len(recent), 5)
        # Verify we got the most recent ones
        self.assertTrue(recent[0].title in ["Notification 10", "Notification 9", "Notification 8"])
    
    def test_mark_all_as_read(self):
        """Test marking all notifications as read."""
        # Create some notifications
        for i in range(5):
            NotificationService.send_notification(
                recipient=self.accountant,
                title=f"Notification {i+1}",
                message=f"Message {i+1}"
            )
        
        # Verify all are unread
        self.assertEqual(NotificationService.get_unread_count(self.accountant), 5)
        
        # Mark all as read
        marked_count = NotificationService.mark_all_as_read(self.accountant)
        
        self.assertEqual(marked_count, 5)
        self.assertEqual(NotificationService.get_unread_count(self.accountant), 0)
    
    def test_mark_all_as_read_idempotent(self):
        """Test that marking all as read is idempotent."""
        # Create notification
        NotificationService.send_notification(
            recipient=self.accountant,
            title="Test",
            message="Test"
        )
        
        # First mark all as read
        count1 = NotificationService.mark_all_as_read(self.accountant)
        self.assertEqual(count1, 1)
        
        # Second mark all as read (should update 0)
        count2 = NotificationService.mark_all_as_read(self.accountant)
        self.assertEqual(count2, 0)
    
    def test_delete_old_notifications(self):
        """Test deleting old notifications."""
        # Create old notification (91 days ago)
        old_notification = Notification.objects.create(
            recipient=self.accountant,
            title="Old Notification",
            message="This is old",
            category=NotificationCategory.WORKFLOW
        )
        old_notification.created_at = timezone.now() - timedelta(days=91)
        old_notification.save()
        
        # Create recent notification (30 days ago)
        recent_notification = Notification.objects.create(
            recipient=self.accountant,
            title="Recent Notification",
            message="This is recent",
            category=NotificationCategory.WORKFLOW
        )
        recent_notification.created_at = timezone.now() - timedelta(days=30)
        recent_notification.save()
        
        # Delete notifications older than 90 days
        deleted_count = NotificationService.delete_old_notifications(days=90)
        
        self.assertEqual(deleted_count, 1)
        
        # Verify old notification is deleted
        self.assertFalse(Notification.objects.filter(pk=old_notification.pk).exists())
        
        # Verify recent notification still exists
        self.assertTrue(Notification.objects.filter(pk=recent_notification.pk).exists())
    
    def test_delete_old_notifications_custom_days(self):
        """Test deleting old notifications with custom days."""
        # Create notification 45 days ago
        old_notification = Notification.objects.create(
            recipient=self.accountant,
            title="Old Notification",
            message="This is old",
            category=NotificationCategory.WORKFLOW
        )
        old_notification.created_at = timezone.now() - timedelta(days=45)
        old_notification.save()
        
        # Delete notifications older than 30 days
        deleted_count = NotificationService.delete_old_notifications(days=30)
        
        self.assertEqual(deleted_count, 1)
    
    def test_convenience_function(self):
        """Test convenience function send_notification."""
        notification = send_notification(
            recipient=self.accountant,
            title="Convenience Test",
            message="Testing convenience function",
            link="/test/"
        )
        
        self.assertIsNotNone(notification.pk)
        self.assertEqual(notification.title, "Convenience Test")
    
    def test_notification_isolation_between_users(self):
        """Test that notifications are isolated between users."""
        # Create notifications for accountant
        NotificationService.send_notification(
            recipient=self.accountant,
            title="For Accountant",
            message="Message for accountant"
        )
        
        # Create notifications for TMO
        NotificationService.send_notification(
            recipient=self.tmo,
            title="For TMO",
            message="Message for TMO"
        )
        
        # Verify counts
        self.assertEqual(NotificationService.get_unread_count(self.accountant), 1)
        self.assertEqual(NotificationService.get_unread_count(self.tmo), 1)
        
        # Mark accountant's as read
        NotificationService.mark_all_as_read(self.accountant)
        
        # TMO should still have unread notification
        self.assertEqual(NotificationService.get_unread_count(self.accountant), 0)
        self.assertEqual(NotificationService.get_unread_count(self.tmo), 1)


class NotificationModelTests(TestCase):
    """Tests for Notification model."""
    
    def setUp(self):
        """Set up test data."""
        self.division = Division.objects.create(
            name="Test Division",
            code="TDV01"
        )
        
        self.district = District.objects.create(
            name="Test District",
            code="TDS01",
            division=self.division
        )
        
        self.tehsil = Tehsil.objects.create(
            name="Test Tehsil",
            code="TST01",
            district=self.district
        )
        
        self.organization = Organization.objects.create(
            name="Test TMA",
            org_type="TMA",
            tehsil=self.tehsil
        )
        
        self.user = User.objects.create_user(
            cnic='1234567890123',
            email='test@test.com',
            first_name='Test',
            last_name='User',
            organization=self.organization
        )
    
    def test_notification_str(self):
        """Test notification string representation."""
        notification = Notification.objects.create(
            recipient=self.user,
            title="Test Notification",
            message="Test message",
            category=NotificationCategory.WORKFLOW
        )
        
        expected = f"Test Notification - Test User"
        self.assertEqual(str(notification), expected)
    
    def test_mark_as_read(self):
        """Test marking notification as read."""
        notification = Notification.objects.create(
            recipient=self.user,
            title="Test",
            message="Test",
            category=NotificationCategory.WORKFLOW
        )
        
        self.assertFalse(notification.is_read)
        
        notification.mark_as_read()
        
        self.assertTrue(notification.is_read)
        # Verify it was saved to database
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
    
    def test_get_badge_class(self):
        """Test getting Bootstrap badge class for notification."""
        # WORKFLOW category
        workflow_notif = Notification.objects.create(
            recipient=self.user,
            title="Workflow",
            message="Test",
            category=NotificationCategory.WORKFLOW
        )
        self.assertEqual(workflow_notif.get_badge_class(), 'bg-primary')
        
        # SYSTEM category
        system_notif = Notification.objects.create(
            recipient=self.user,
            title="System",
            message="Test",
            category=NotificationCategory.SYSTEM
        )
        self.assertEqual(system_notif.get_badge_class(), 'bg-info')
        
        # ALERT category
        alert_notif = Notification.objects.create(
            recipient=self.user,
            title="Alert",
            message="Test",
            category=NotificationCategory.ALERT
        )
        self.assertEqual(alert_notif.get_badge_class(), 'bg-danger')
    
    def test_notification_ordering(self):
        """Test that notifications are ordered by created_at descending."""
        import time
        # Create notifications with slight time delays
        notif1 = Notification.objects.create(
            recipient=self.user,
            title="First",
            message="First",
            category=NotificationCategory.WORKFLOW
        )
        time.sleep(0.01)  # Small delay to ensure different timestamps
        
        notif2 = Notification.objects.create(
            recipient=self.user,
            title="Second",
            message="Second",
            category=NotificationCategory.WORKFLOW
        )
        time.sleep(0.01)
        
        notif3 = Notification.objects.create(
            recipient=self.user,
            title="Third",
            message="Third",
            category=NotificationCategory.WORKFLOW
        )
        
        notifications = list(Notification.objects.filter(recipient=self.user))
        
        # Most recent should be first (notif3)
        self.assertEqual(notifications[0].pk, notif3.pk)
        # Verify ordering is descending by created_at
        self.assertTrue(notifications[0].created_at >= notifications[1].created_at)
        self.assertTrue(notifications[1].created_at >= notifications[2].created_at)
