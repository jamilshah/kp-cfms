"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Custom User model with role-based access control (RBAC).
             Implements the Maker/Checker/Approver hierarchy with
             multi-tenancy support. Uses database-driven Role model
             for dynamic permissions.
-------------------------------------------------------------------------
"""
import uuid
from typing import Optional, List
from django.contrib.auth.models import AbstractUser, BaseUserManager, Group
from django.db import models
from django.utils.translation import gettext_lazy as _


class RoleCode(models.TextChoices):
    """
    Standard role codes for the system.
    
    These are used as reference codes when creating Role objects.
    """
    SUPER_ADMIN = 'SUPER_ADMIN', _('Super Administrator')
    LCB_OFFICER = 'LCB_OFFICER', _('LCB Finance Officer')
    TMO = 'TMO', _('Tehsil Municipal Officer')
    TMA_ADMIN = 'TMA_ADMIN', _('TMA Administrator')
    FINANCE_OFFICER = 'FINANCE_OFFICER', _('Finance Officer (Pre-Audit)')
    ACCOUNTANT = 'ACCOUNTANT', _('Accountant (Verifier)')
    CASHIER = 'CASHIER', _('Cashier')
    BUDGET_OFFICER = 'BUDGET_OFFICER', _('Budget Officer')
    DEALING_ASSISTANT = 'DEALING_ASSISTANT', _('Dealing Assistant (Maker)')


class Role(models.Model):
    """
    Dynamic Role model for database-driven RBAC.
    
    Linked 1-to-1 with Django's Group model to leverage standard
    Django permissions system. Roles can be assigned to users
    via ManyToMany relationship.
    
    Attributes:
        name: Human-readable role name.
        code: Unique slug identifier for the role.
        description: Detailed description of the role's responsibilities.
        group: Associated Django Group for permission management.
        is_system_role: If True, role cannot be deleted by users.
    """
    
    name = models.CharField(
        max_length=100,
        verbose_name=_('Role Name'),
        help_text=_('Human-readable name for the role.')
    )
    code = models.SlugField(
        max_length=50,
        unique=True,
        verbose_name=_('Role Code'),
        help_text=_('Unique identifier code (e.g., TMO, ACCOUNTANT).')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Detailed description of role responsibilities.')
    )
    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name='cfms_role',
        verbose_name=_('Django Group'),
        help_text=_('Associated Django Group for permissions.')
    )
    is_system_role = models.BooleanField(
        default=False,
        verbose_name=_('System Role'),
        help_text=_('System roles cannot be deleted by users.')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Role')
        verbose_name_plural = _('Roles')
        ordering = ['name']
    
    def __str__(self) -> str:
        return self.name
    
    def save(self, *args, **kwargs):
        """Create or update the associated Django Group."""
        if not self.pk:
            # Creating new role - create Django Group first
            group, created = Group.objects.get_or_create(name=self.name)
            self.group = group
        else:
            # Updating role - update Group name if changed
            if self.group and self.group.name != self.name:
                self.group.name = self.name
                self.group.save()
        super().save(*args, **kwargs)
    
    @classmethod
    def get_by_code(cls, code: str) -> Optional['Role']:
        """
        Get a role by its code.
        
        Args:
            code: The role code to look up.
            
        Returns:
            Role instance or None if not found.
        """
        try:
            return cls.objects.get(code=code)
        except cls.DoesNotExist:
            return None


# Keep UserRole for backward compatibility during migration
class UserRole(models.TextChoices):
    """
    Enumeration of user roles in the TMA hierarchy.
    
    DEPRECATED: Use Role model instead. Kept for migration compatibility.
    
    Based on the KP TMA Budget Rules 2016:
    - Dealing Assistant (Maker): Creates bills and budget entries
    - Accountant (Checker): Pre-audits and verifies transactions
    - TMO (Approver): Final approval authority for Local posts
    - TO Finance: Budget oversight and releases
    - LCB Finance Officer: Provincial oversight, approves PUGF posts
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
        # Remove role from extra_fields if present (handled via roles M2M)
        extra_fields.pop('role', None)
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
        # Remove role from extra_fields (deprecated field)
        extra_fields.pop('role', None)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        
        user = self.create_user(cnic, email, password, **extra_fields)
        
        # Assign SUPER_ADMIN role if it exists
        super_admin_role = Role.get_by_code('SUPER_ADMIN')
        if super_admin_role:
            user.roles.add(super_admin_role)
        
        return user


class CustomUser(AbstractUser):
    """
    Custom User model for KP-CFMS.
    
    Uses CNIC (National Identity Card) as the unique identifier
    instead of username. Implements role-based access control
    with multi-tenancy support.
    
    Attributes:
        cnic: Unique 13-digit CNIC number.
        email: User's email address.
        role: User's role in the TMA hierarchy.
        organization: The TMA/Organization this user belongs to (nullable for LCB/LGD).
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
        verbose_name=_('Role (Deprecated)'),
        help_text=_('DEPRECATED: Use roles field instead. Kept for migration.')
    )
    
    # New dynamic roles system
    roles = models.ManyToManyField(
        Role,
        blank=True,
        related_name='users',
        verbose_name=_('Roles'),
        help_text=_('Roles assigned to this user.')
    )
    
    # Multi-tenancy: Link user to their organization
    # NULL for LCB/LGD users who have oversight across all organizations
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='users',
        verbose_name=_('Organization'),
        help_text=_('TMA this user belongs to. Null for LCB/LGD oversight staff.')
    )
    
    designation = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Designation'),
        help_text=_('Official job title (e.g., Junior Clerk, Superintendent).')
    )
    department = models.ForeignKey(
        'budgeting.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name=_('Department'),
        help_text=_('Department/wing this user belongs to for access control.')
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
    
    def save(self, *args, **kwargs):
        """Normalize CNIC by stripping non-digit characters before saving."""
        if self.cnic:
            import re
            self.cnic = re.sub(r'\D', '', self.cnic)
        super().save(*args, **kwargs)
    
    def __str__(self) -> str:
        """Return user's full name and role."""
        return f"{self.get_full_name()} ({self.get_role_display()})"
    
    def get_full_name(self) -> str:
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self) -> str:
        """Return the user's first name."""
        return self.first_name
    
    def get_role_display(self) -> str:
        """Return comma-separated list of role names."""
        role_names = list(self.roles.values_list('name', flat=True))
        if role_names:
            return ', '.join(role_names)
        # Fallback to legacy role field
        if self.role:
            return dict(UserRole.choices).get(self.role, self.role)
        return 'No Role'
    
    def has_role(self, role_code: str) -> bool:
        """
        Check if user has a specific role by code.
        
        Args:
            role_code: The role code to check (e.g., 'TMO', 'ACCOUNTANT').
            
        Returns:
            True if user has the role, False otherwise.
        """
        return self.roles.filter(code=role_code).exists()
    
    def has_any_role(self, role_codes: List[str]) -> bool:
        """
        Check if user has any of the specified roles.
        
        Args:
            role_codes: List of role codes to check.
            
        Returns:
            True if user has any of the roles, False otherwise.
        """
        if self.is_superuser:
            return True
        return self.roles.filter(code__in=role_codes).exists()
    
    def get_role_codes(self) -> List[str]:
        """Return list of role codes assigned to this user."""
        return list(self.roles.values_list('code', flat=True))
    
    # Role-checking methods for RBAC (updated to use new roles M2M)
    def is_maker(self) -> bool:
        """Check if user has Maker (Dealing Assistant) role."""
        return self.has_any_role(['DEALING_ASSISTANT', 'DA'])
    
    def is_checker(self) -> bool:
        """Check if user has Checker (Accountant) role."""
        return self.has_any_role(['ACCOUNTANT', 'AC'])
    
    def is_approver(self) -> bool:
        """Check if user has Approver (TMO) role."""
        return self.has_any_role(['TMO'])
    
    def is_finance_officer(self) -> bool:
        """Check if user has Finance Officer role."""
        return self.has_any_role(['FINANCE_OFFICER', 'TOF', 'TO_FINANCE'])
    
    def is_cashier(self) -> bool:
        """Check if user has Cashier role."""
        return self.has_any_role(['CASHIER', 'CSH'])
    
    def is_lcb_officer(self) -> bool:
        """Check if user has LCB Finance Officer role."""
        return self.has_any_role(['LCB_OFFICER', 'LCB'])
    
    def is_budget_officer(self) -> bool:
        """Check if user has Budget Officer role."""
        return self.has_any_role(['BUDGET_OFFICER'])
    
    def is_tma_admin(self) -> bool:
        """Check if user has TMA Administrator role."""
        return self.has_role('TMA_ADMIN')
    
    def is_super_admin(self) -> bool:
        """Check if user is Provincial Super Admin (superuser with no org)."""
        return self.is_superuser and self.organization is None
    
    def is_lcb_admin(self) -> bool:
        """
        Check if user is an LCB admin with cross-tenant access.
        
        LCB admins have organization=None and role=LCB.
        They can view all TMAs but have restricted write access.
        """
        return self.is_lcb_officer() and self.organization is None
    
    def is_oversight_user(self) -> bool:
        """
        Check if user has oversight access (LCB/LGD/Admin without org).
        
        Oversight users can view all organizations but have
        restricted write permissions (only status changes).
        """
        return self.organization is None and (
            self.is_lcb_officer() or self.is_super_admin()
        )
    
    def can_access_organization(self, org) -> bool:
        """
        Check if user can access data from the given organization.
        
        Args:
            org: The Organization to check access for.
            
        Returns:
            True if user can access the organization's data.
        """
        # Oversight users can access all orgs
        if self.is_oversight_user():
            return True
        # Regular users can only access their own org
        return self.organization_id == org.id
    
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
    
    def can_approve_pugf_posts(self) -> bool:
        """
        Check if user can approve PUGF posts (LCB only).
        
        PUGF posts require LCB approval, not TMO approval.
        """
        return self.is_lcb_officer() or self.is_superuser
    
    def can_recommend_pugf_posts(self) -> bool:
        """
        Check if user can recommend (not approve) PUGF posts.
        
        TMO can recommend PUGF posts but LCB must approve.
        """
        return self.is_approver() or self.is_superuser
    
    def should_see_own_department_only(self) -> bool:
        """
        Check if user should see only their own department's data.
        
        Returns True if ALL of the following conditions are met:
        1. Organization has enforce_department_isolation enabled
        2. User is NOT a superuser
        3. User is NOT TMO, Finance Officer, or TMA Admin (they see all departments)
        4. User has a department assigned
        
        Returns:
            True if user should see only their department's data, False otherwise.
        """
        # Superusers always see everything
        if self.is_superuser:
            return False
        
        # No organization = oversight user, see everything
        if not self.organization:
            return False
        
        # Check if organization has department isolation enabled
        if not getattr(self.organization, 'enforce_department_isolation', False):
            return False
        
        # These roles always see all departments regardless of setting
        if self.is_approver() or self.is_finance_officer() or self.is_tma_admin():
            return False
        
        # User must have a department assigned to filter by it
        if not self.department:
            return False
        
        return True
    
    def get_accessible_departments(self):
        """
        Get QuerySet of departments this user can access.
        
        Returns:
            - All departments if user shouldn't be filtered
            - Only user's department if filtering is enabled
        """
        from apps.budgeting.models import Department
        
        if not self.should_see_own_department_only():
            # User can see all departments
            return Department.objects.filter(is_active=True)
        
        # User can only see their own department
        if self.department:
            return Department.objects.filter(id=self.department.id)
        
        return Department.objects.none()
