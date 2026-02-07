"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Management command to cleanup old notifications
Usage: python manage.py cleanup_notifications --days=90 [--dry-run]
-------------------------------------------------------------------------
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta
from apps.core.models import Notification
from apps.core.services import NotificationService
from django.db import models # Added import

class Command(BaseCommand):
    help = 'Delete read notifications older than specified days'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Delete notifications older than this many days (default: 90)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--unread-days',
            type=int,
            default=180,
            help='Delete even unread notifications older than this many days (default: 180)'
        )
        parser.add_argument(
            '--keep-alerts',
            action='store_true',
            help='Keep ALERT category notifications regardless of age'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        unread_days = options['unread_days']
        dry_run = options['dry_run']
        keep_alerts = options['keep_alerts']
        
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write(
            self.style.WARNING('KP-CFMS Notification Cleanup Utility')
        )
        self.stdout.write(self.style.WARNING('=' * 70))
        
        # Calculate cutoff dates
        read_cutoff = timezone.now() - timedelta(days=days)
        unread_cutoff = timezone.now() - timedelta(days=unread_days)
        
        # Build query for read notifications
        read_query = Notification.objects.filter(
            is_read=True,
            created_at__lt=read_cutoff
        )
        
        # Build query for very old unread notifications
        unread_query = Notification.objects.filter(
            is_read=False,
            created_at__lt=unread_cutoff
        )
        
        # Exclude alerts if requested
        if keep_alerts:
            from apps.core.models import NotificationCategory
            read_query = read_query.exclude(category=NotificationCategory.ALERT)
            unread_query = unread_query.exclude(category=NotificationCategory.ALERT)
        
        # Count notifications
        read_count = read_query.count()
        unread_count = unread_query.count()
        total_count = read_count + unread_count
        
        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS('✓ No notifications to cleanup. Database is clean.')
            )
            return
        
        # Show statistics
        self.stdout.write('')
        self.stdout.write('Cleanup Summary:')
        self.stdout.write(f'  • Read notifications older than {days} days: {read_count}')
        self.stdout.write(f'  • Unread notifications older than {unread_days} days: {unread_count}')
        self.stdout.write(f'  • Total to delete: {total_count}')
        
        if keep_alerts:
            self.stdout.write('  • Keeping ALERT notifications regardless of age')
        
        # Show breakdown by category
        if total_count > 0:
            self.stdout.write('')
            self.stdout.write('Breakdown by Category:')
            
            combined_query = read_query | unread_query
            categories = combined_query.values('category').annotate(
                count=models.Count('id')
            ).order_by('-count')
            
            for cat in categories:
                self.stdout.write(
                    f"  • {cat['category']}: {cat['count']} notifications"
                )
        
        # Dry run - just show what would be deleted
        if dry_run:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN MODE: No notifications were deleted.'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    f'Run without --dry-run flag to actually delete {total_count} notifications.'
                )
            )
            return
        
        # Confirm deletion - Force yes for non-interactive execution if needed, but standard is input
        # Note: In a real automated task, we'd use --no-input or similar, but here we keep interactive
        # for manual running. 
        self.stdout.write('')
        # Skip input for this environment as it might hang? No, user can run it.
        # But for 'run_command' tool usage, input might be tricky.
        # I will assume the user runs this manually.
        
        confirm = input(
            self.style.WARNING(
                f'⚠️  Are you sure you want to delete {total_count} notifications? (yes/no): '
            )
        )
        
        if confirm.lower() != 'yes':
            self.stdout.write(
                self.style.ERROR('Cleanup cancelled by user.')
            )
            return
        
        # Perform deletion
        try:
            self.stdout.write('')
            self.stdout.write('Deleting notifications...')
            
            read_deleted = read_query.delete()[0]
            unread_deleted = unread_query.delete()[0]
            total_deleted = read_deleted + unread_deleted
            
            self.stdout.write('')
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Successfully deleted {total_deleted} notifications'
                )
            )
            self.stdout.write(f'  • Read: {read_deleted}')
            self.stdout.write(f'  • Unread: {unread_deleted}')
            
            # Log to file
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f'Notification cleanup: deleted {total_deleted} notifications '
                f'(read: {read_deleted}, unread: {unread_deleted})',
                extra={
                    'total_deleted': total_deleted,
                    'read_deleted': read_deleted,
                    'unread_deleted': unread_deleted,
                    'days': days,
                    'unread_days': unread_days,
                }
            )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Error during cleanup: {str(e)}')
            )
            raise CommandError(f'Cleanup failed: {str(e)}')
