"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Custom User model with role-based access control (RBAC).
             Implements the Maker/Checker/Approver hierarchy.
-------------------------------------------------------------------------
"""
import uuid
from typing import Optional, List
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserRole(models.TextChoices):
    """
    Enumeration of user roles in the TMA hierarchy.
    
    Based on the KP TMA Budget Rules 2016:
    - Dealing Assistant (Maker): Creates bills and budget entries
    - Accountant (Checker): Pre-audits and verifies transactions
    - TMO (Approver): Final approval authority
    - TO Finance: Budget oversight and releases
    - LCB Finance Officer: Provincial oversight
    - Cashier: Records payments and collections
    - System Admin: System configuration
    """
    
    DEALING_ASSISTANT = 'DA', _('Dealing Assistant (Maker)')
    ACCOUNTANT = 'AC', _('Accountant (Checker)')
    TMO = 'TMO', _('Tehsil Municipal Officer (Approver)')
    TO_FINANCE = 'TOF', _('Tehsil Officer Finance')
    LCB_OFFICER = 'LCB', _('LCB Finance Officer')
    CASHIER = 'CSH', _('Cashier')
    SYSTEM_ADMIN = 'ADM', _('System Administrator')


class CustomUserManager(BaseUserManager):
    """
    Custom manager for CustomUser model.
    
    Provides methods to create regular users and superusers with
    proper validation of required fields.
    """
    
    def create_user(
        self,
        cnic: str,
        email: str,
        password: Optional[str] = None,
        **extra_fields
    ) -> 'CustomUser':
        """
        Create and return a regular user.
        
        Args:
            cnic: National Identity Card number (unique identifier).
            email: User's email address.
            password: User's password.
            **extra_fields: Additional fields for the user model.
            
        Returns:
            The created CustomUser instance.
            
        Raises:
            ValueError: If cnic is not provided.
        """
        if not cnic:
            raise ValueError(_('CNIC is required for user creation.'))
        
        email = self.normalize_email(email)
        user = self.model(cnic=cnic, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(
        self,
        cnic: str,
        email: str,
        password: Optional[str] = None,
        **extra_fields
    ) -> 'CustomUser':
        """
        Create and return a superuser.
        
        Args:
            cnic: National Identity Card number.
            email: User's email address.
            password: User's password.
            **extra_fields: Additional fields for the user model.
            
        Returns:
            The created superuser CustomUser instance.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', UserRole.SYSTEM_ADMIN)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        
        return self.create_user(cnic, email, password, **extra_fields)


class CustomUser(AbstractUser):
    """
    Custom User model for KP-CFMS.
    
    Uses CNIC (National Identity Card) as the unique identifier
    instead of username. Implements role-based access control.
    
    Attributes:
        cnic: Unique 13-digit CNIC number.
        email: User's email address.
        role: User's role in the TMA hierarchy.
        designation: Official job title.
        department: Associated department/wing.
        phone: Contact phone number.
    """
    
    # Remove username field, use CNIC instead
    username = None
    
    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name=_('Public ID'),
        help_text=_('Unique UUID for external reference.')
    )
    
    cnic = models.CharField(
        max_length=15,
        unique=True,
        verbose_name=_('CNIC'),
        help_text=_('13-digit National Identity Card number (e.g., 12345-1234567-1).')
    )
    email = models.EmailField(
        unique=True,
        verbose_name=_('Email Address')
    )
    role = models.CharField(
        max_length=5,
        choices=UserRole.choices,
        default=UserRole.DEALING_ASSISTANT,
        verbose_name=_('Role'),
        help_text=_('User role in the TMA hierarchy.')
    )
    designation = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Designation'),
        help_text=_('Official job title (e.g., Junior Clerk, Superintendent).')
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Department'),
        help_text=_('Associated department or wing.')
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Phone Number')
    )
    
    # Override first_name and last_name for better display
    first_name = models.CharField(
        max_length=150,
        verbose_name=_('First Name')
    )
    last_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_('Last Name')
    )
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'cnic'
    REQUIRED_FIELDS = ['email', 'first_name']
    
    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['first_name', 'last_name']
    
    def __str__(self) -> str:
        """Return user's full name and role."""
        return f"{self.get_full_name()} ({self.get_role_display()})"
    
    def get_full_name(self) -> str:
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self) -> str:
        """Return the user's first name."""
        return self.first_name
    
    # Role-checking methods for RBAC
    def is_maker(self) -> bool:
        """Check if user has Maker (Dealing Assistant) role."""
        return self.role == UserRole.DEALING_ASSISTANT
    
    def is_checker(self) -> bool:
        """Check if user has Checker (Accountant) role."""
        return self.role == UserRole.ACCOUNTANT
    
    def is_approver(self) -> bool:
        """Check if user has Approver (TMO) role."""
        return self.role == UserRole.TMO
    
    def is_finance_officer(self) -> bool:
        """Check if user has TO Finance role."""
        return self.role == UserRole.TO_FINANCE
    
    def is_cashier(self) -> bool:
        """Check if user has Cashier role."""
        return self.role == UserRole.CASHIER
    
    def is_lcb_officer(self) -> bool:
        """Check if user has LCB Finance Officer role."""
        return self.role == UserRole.LCB_OFFICER
    
    def can_create_bills(self) -> bool:
        """Check if user can create bills (Maker role)."""
        return self.is_maker() or self.is_superuser
    
    def can_verify_bills(self) -> bool:
        """Check if user can verify bills (Checker role)."""
        return self.is_checker() or self.is_superuser
    
    def can_approve_bills(self) -> bool:
        """Check if user can approve bills (Approver role)."""
        return self.is_approver() or self.is_superuser
    
    def can_release_funds(self) -> bool:
        """Check if user can release budget funds."""
        return self.is_finance_officer() or self.is_approver() or self.is_superuser
    
    def can_record_payments(self) -> bool:
        """Check if user can record payments/collections."""
        return self.is_cashier() or self.is_superuser
    
    def can_approve_coa_requests(self) -> bool:
        """Check if user can approve Chart of Accounts requests."""
        return self.is_lcb_officer() or self.is_superuser
