"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Reusable model mixins for audit logging and timestamps.
-------------------------------------------------------------------------
"""
import uuid
from typing import Optional
from django.db import models
from django.conf import settings


class UUIDMixin(models.Model):
    """
    Abstract mixin that adds a public_id UUID field.
    
    Used for external references (APIs, URLs) while keeping
    integer IDs for internal foreign keys.
    """
    
    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="Public ID",
        help_text="Unique UUID for external reference."
    )
    
    class Meta:
        abstract = True


class TimeStampedMixin(UUIDMixin):
    """
    Abstract mixin that adds created_at and updated_at timestamps.
    
    Attributes:
        created_at: Timestamp when the record was created.
        updated_at: Timestamp when the record was last modified.
    """
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At",
        help_text="Timestamp when this record was created."
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At",
        help_text="Timestamp when this record was last modified."
    )
    
    class Meta:
        abstract = True


class AuditLogMixin(TimeStampedMixin):
    """
    Abstract mixin that adds audit trail fields for user tracking.
    
    Extends TimeStampedMixin with created_by and updated_by fields
    to track which user created or modified a record.
    
    Attributes:
        created_by: ForeignKey to the user who created the record.
        updated_by: ForeignKey to the user who last modified the record.
    """
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)s_created",
        null=True,
        blank=True,
        verbose_name="Created By",
        help_text="User who created this record."
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)s_updated",
        null=True,
        blank=True,
        verbose_name="Updated By",
        help_text="User who last modified this record."
    )
    
    class Meta:
        abstract = True
    
    def save_with_user(self, user: Optional[object] = None, *args, **kwargs) -> None:
        """
        Save the model while setting the audit user fields.
        
        Args:
            user: The user performing the save operation.
            *args: Additional positional arguments for save().
            **kwargs: Additional keyword arguments for save().
        """
        if user is not None:
            if self.pk is None:
                self.created_by = user
            self.updated_by = user
        self.save(*args, **kwargs)


class StatusMixin(models.Model):
    """
    Abstract mixin for models that follow a state machine workflow.
    
    Provides is_active flag and status field foundation.
    """
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Is Active",
        help_text="Whether this record is active in the system."
    )
    
    class Meta:
        abstract = True
