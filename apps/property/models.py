"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Property Management models for TMA GIS System
             Integrated with CFMS Revenue Module
-------------------------------------------------------------------------
"""
from decimal import Decimal
from django.db import models, IntegrityError, transaction
from django.core.validators import MinValueValidator, URLValidator, RegexValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.urls import reverse
from builtins import property as _property  # Import to avoid name conflict with ForeignKey field

from apps.core.mixins import AuditLogMixin, StatusMixin, TenantAwareMixin, TimeStampedMixin
from apps.core.models import District as CoreDistrict


# ============================================================================
# CHOICE FIELDS
# ============================================================================

class PropertyType(models.TextChoices):
    """Property type classification."""
    COMMERCIAL = 'COMMERCIAL', _('Commercial')
    RESIDENTIAL = 'RESIDENTIAL', _('Residential')
    INDUSTRIAL = 'INDUSTRIAL', _('Industrial')
    AGRICULTURAL = 'AGRICULTURAL', _('Agricultural')
    INSTITUTIONAL = 'INSTITUTIONAL', _('Institutional')
    MIXED_USE = 'MIXED_USE', _('Mixed Use')


class PropertySubType(models.TextChoices):
    """Detailed property classification."""
    # Commercial
    SHOP = 'SHOP', _('Shop')
    PLAZA = 'PLAZA', _('Plaza/Building')
    OFFICE = 'OFFICE', _('Office')
    WAREHOUSE = 'WAREHOUSE', _('Warehouse')
    MARKET = 'MARKET', _('Market')
    
    # Residential
    HOUSE = 'HOUSE', _('House')
    APARTMENT = 'APARTMENT', _('Apartment')
    FLAT = 'FLAT', _('Flat')
    
    # Land
    PLOT = 'PLOT', _('Vacant Plot')
    LAND = 'LAND', _('Agricultural Land')
    
    # Other
    PARKING = 'PARKING', _('Parking Space')
    OTHER = 'OTHER', _('Other')


class PropertyStatus(models.TextChoices):
    """Property occupancy status."""
    RENTED_OUT = 'RENTED_OUT', _('Rented Out')
    VACANT = 'VACANT', _('Vacant')
    SELF_USE = 'SELF_USE', _('Self Use (TMA)')
    UNDER_LITIGATION = 'UNDER_LITIGATION', _('Under Litigation')
    UNDER_CONSTRUCTION = 'UNDER_CONSTRUCTION', _('Under Construction')
    DEMOLISHED = 'DEMOLISHED', _('Demolished')
    ENCROACHED = 'ENCROACHED', _('Encroached')


class CourtCaseStatus(models.TextChoices):
    """Litigation status."""
    NO_CASE = 'NO_CASE', _('No Case')
    PENDING = 'PENDING', _('Case Pending')
    DECIDED_FAVOR = 'DECIDED_FAVOR', _('Decided in Favor')
    DECIDED_AGAINST = 'DECIDED_AGAINST', _('Decided Against')
    UNDER_APPEAL = 'UNDER_APPEAL', _('Under Appeal')


class LeaseStatus(models.TextChoices):
    """Lease agreement status."""
    DRAFT = 'DRAFT', _('Draft')
    ACTIVE = 'ACTIVE', _('Active')
    EXPIRED = 'EXPIRED', _('Expired')
    TERMINATED = 'TERMINATED', _('Terminated')
    RENEWED = 'RENEWED', _('Renewed')


# ============================================================================
# GEOGRAPHIC MASTER DATA (Linked to Core)
# ============================================================================


class Mauza(TimeStampedMixin):
    """
    Mauza / Revenue Estate master data.
    
    Mauza is the smallest revenue unit in Pakistan's land administration.
    Links to core.District from the core app.
    
    Attributes:
        name: Mauza name (e.g., Abadai Peshawar)
        district: Parent district (from core app)
        code: Mauza code
    """
    name = models.CharField(
        max_length=200,
        verbose_name=_('Mauza Name')
    )
    district = models.ForeignKey(
        'core.District',
        on_delete=models.PROTECT,
        related_name='property_mauzas',
        verbose_name=_('District')
    )
    code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Mauza Code')
    )
    
    class Meta:
        verbose_name = _('Mauza')
        verbose_name_plural = _('Mauzas')
        unique_together = ['name', 'district']
        ordering = ['district__name', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.district.name})"


class Village(TimeStampedMixin):
    """
    Village / Neighbourhood Council.
    
    Attributes:
        name: Village/Neighbourhood name
        mauza: Parent mauza
        code: Village code
    """
    name = models.CharField(
        max_length=200,
        verbose_name=_('Village/Neighbourhood Name')
    )
    mauza = models.ForeignKey(
        Mauza,
        on_delete=models.PROTECT,
        related_name='villages',
        verbose_name=_('Mauza')
    )
    code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Village Code')
    )
    
    class Meta:
        verbose_name = _('Village/Neighbourhood')
        verbose_name_plural = _('Villages/Neighbourhoods')
        unique_together = ['name', 'mauza']
        ordering = ['mauza__name', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.mauza.name})"


# ============================================================================
# PROPERTY MODEL
# ============================================================================

class Property(AuditLogMixin, TenantAwareMixin):
    """
    Main Property model.
    
    Represents a single property (shop, building, land) owned by the TMA.
    """
    
    # Basic Information
    property_code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_('Property Code'),
        help_text=_('Unique identifier (e.g., PSH-COM-001)')
    )
    name = models.CharField(
        max_length=200,
        verbose_name=_('Property Name'),
        help_text=_('e.g., Shop No. 1-A, House 123')
    )
    property_type = models.CharField(
        max_length=20,
        choices=PropertyType.choices,
        default=PropertyType.COMMERCIAL,
        verbose_name=_('Property Type')
    )
    property_sub_type = models.CharField(
        max_length=20,
        choices=PropertySubType.choices,
        default=PropertySubType.SHOP,
        verbose_name=_('Property Sub-Type')
    )
    status = models.CharField(
        max_length=30,
        choices=PropertyStatus.choices,
        default=PropertyStatus.VACANT,
        verbose_name=_('Property Status')
    )
    
    # Location
    address = models.TextField(
        verbose_name=_('Complete Address')
    )
    district = models.ForeignKey(
        'core.District',
        on_delete=models.PROTECT,
        related_name='properties',
        verbose_name=_('District')
    )
    mauza = models.ForeignKey(
        Mauza,
        on_delete=models.PROTECT,
        related_name='properties',
        verbose_name=_('Mauza/Revenue Estate')
    )
    village = models.ForeignKey(
        Village,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='properties',
        verbose_name=_('Village/Neighbourhood')
    )
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        verbose_name=_('Latitude'),
        help_text=_('GPS Latitude (e.g., 34.0082744)')
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        verbose_name=_('Longitude'),
        help_text=_('GPS Longitude (e.g., 71.5731692)')
    )
    
    # Area (in Marlas - Pakistani unit)
    area_marlas = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.0001'))],
        verbose_name=_('Area (Marlas)'),
        help_text=_('1 Marla = 225 sq.ft = 20.9 sq.m')
    )
    area_sqft = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False,
        null=True,
        blank=True,
        verbose_name=_('Area (Sq.Ft)'),
        help_text=_('Auto-calculated from Marlas')
    )
    area_sqm = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False,
        null=True,
        blank=True,
        verbose_name=_('Area (Sq.M)'),
        help_text=_('Auto-calculated from Marlas')
    )
    
    # Ownership & Legal
    ownership_title = models.CharField(
        max_length=500,
        verbose_name=_('Ownership Title'),
        help_text=_('As per land revenue record')
    )
    survey_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Survey/Khasra Number')
    )
    acquisition_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Acquisition Date'),
        help_text=_('Date when property was acquired by TMA')
    )
    acquisition_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Acquisition Cost'),
        help_text=_('Original cost when acquired by TMA')
    )
    
    # Financial
    current_market_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Current Market Value'),
        help_text=_('Current estimated market value')
    )
    last_valuation_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Last Valuation Date'),
        help_text=_('Date of last property valuation')
    )
    annual_rent = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Annual Rent'),
        help_text=_('Annual rent amount')
    )
    monthly_rent = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        editable=False,
        null=True,
        blank=True,
        verbose_name=_('Monthly Rent'),
        help_text=_('Auto-calculated (Annual / 12)')
    )
    last_rent_revision = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Last Rent Revision Date')
    )
    
    # Tenant Information - DEPRECATED: Use PropertyLease model instead
    # Keeping these fields temporarily for data migration
    # TODO: Remove after migrating to PropertyLease
    
    # Litigation
    court_case_status = models.CharField(
        max_length=20,
        choices=CourtCaseStatus.choices,
        default=CourtCaseStatus.NO_CASE,
        verbose_name=_('Court Case Status')
    )
    court_case_title = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Case Title/Description')
    )
    court_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Name of Court')
    )
    case_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Court Case Number')
    )
    next_hearing_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Next Hearing Date')
    )
    
    # Future Plans & Remarks
    future_use = models.TextField(
        blank=True,
        verbose_name=_('Future Use/Plans')
    )
    remarks = models.TextField(
        blank=True,
        verbose_name=_('Remarks/Notes')
    )
    
    # Is Active
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active')
    )
    
    class Meta:
        verbose_name = _('Property')
        verbose_name_plural = _('Properties')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['property_code']),
            models.Index(fields=['status']),
            models.Index(fields=['property_type']),
            models.Index(fields=['district', 'mauza']),
            models.Index(fields=['latitude', 'longitude']),  # GIS performance
            models.Index(fields=['annual_rent']),  # Revenue analysis
        ]
    
    def __str__(self):
        return f"{self.property_code} - {self.name}"
    
    def save(self, *args, **kwargs):
        """Override save to auto-calculate area conversions and monthly rent."""
        # Calculate area conversions (1 Marla = 225 sq.ft = 20.9 sq.m)
        if self.area_marlas is not None:
            self.area_sqft = self.area_marlas * Decimal('225.00')
            self.area_sqm = self.area_marlas * Decimal('20.90')
        else:
            self.area_sqft = None
            self.area_sqm = None
        
        # Calculate monthly rent
        if self.annual_rent is not None:
            self.monthly_rent = self.annual_rent / Decimal('12.00')
        else:
            self.monthly_rent = None
        
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        """Return URL for property detail page."""
        return reverse('property:detail', kwargs={'pk': self.pk})
    
    @_property
    def current_lease(self):
        """Get the current active lease for this property."""
        return self.leases.filter(status=LeaseStatus.ACTIVE).first()
    
    @_property
    def current_tenant(self):
        """Get current tenant from active lease."""
        lease = self.current_lease
        return lease.tenant if lease else None
    
    def is_rented(self):
        """Check if property is currently rented."""
        return self.status == PropertyStatus.RENTED_OUT
    
    def is_vacant(self):
        """Check if property is vacant."""
        return self.status == PropertyStatus.VACANT
    
    def has_litigation(self):
        """Check if property has active court case."""
        return self.court_case_status in [
            CourtCaseStatus.PENDING,
            CourtCaseStatus.UNDER_APPEAL
        ]
    
    def get_marker_color(self):
        """Get marker color for GIS map based on status."""
        color_map = {
            PropertyStatus.RENTED_OUT: 'green',
            PropertyStatus.VACANT: 'red',
            PropertyStatus.UNDER_LITIGATION: 'orange',
            PropertyStatus.SELF_USE: 'blue',
            PropertyStatus.UNDER_CONSTRUCTION: 'yellow',
            PropertyStatus.DEMOLISHED: 'gray',
            PropertyStatus.ENCROACHED: 'purple',
        }
        return color_map.get(self.status, 'gray')


# ============================================================================
# PROPERTY LEASE MODEL
# ============================================================================

class PropertyLease(AuditLogMixin, TenantAwareMixin):
    """
    Property Lease/Tenancy Agreement.
    
    Tracks rental agreements with tenants, supporting full lease history.
    One property can have multiple leases over time (historical), but only
    one ACTIVE lease at a time.
    
    Attributes:
        property: The property being leased
        tenant: Tenant from revenue.Payer model
        lease_number: Unique lease agreement number
        lease_start_date: Start date of lease
        lease_end_date: End date (null = month-to-month)
        monthly_rent: Rent per month
        security_deposit: Security/advance payment
        status: DRAFT, ACTIVE, EXPIRED, TERMINATED, RENEWED
    """
    
    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name='leases',
        verbose_name=_('Property')
    )
    tenant = models.ForeignKey(
        'revenue.Payer',
        on_delete=models.PROTECT,
        related_name='property_leases',
        verbose_name=_('Tenant'),
        help_text=_('Tenant from Payer registry')
    )
    
    # Lease Identification
    lease_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_('Lease Agreement Number'),
        help_text=_('Unique lease reference (e.g., LEASE-2026-001)')
    )
    
    # Lease Period
    lease_start_date = models.DateField(
        verbose_name=_('Lease Start Date')
    )
    lease_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Lease End Date'),
        help_text=_('Leave blank for month-to-month tenancy')
    )
    
    # Financial Terms
    monthly_rent = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Monthly Rent Amount')
    )
    security_deposit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Security Deposit'),
        help_text=_('Advance/security deposit amount')
    )
    annual_increment_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Annual Increment (%)'),
        help_text=_('Annual rent increase percentage')
    )
    
    # Lease Status
    status = models.CharField(
        max_length=15,
        choices=LeaseStatus.choices,
        default=LeaseStatus.DRAFT,
        verbose_name=_('Lease Status')
    )
    
    # Agreement Details
    agreement_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Agreement Signed Date')
    )
    agreement_document = models.FileField(
        upload_to='lease_agreements/%Y/%m/',
        blank=True,
        null=True,
        verbose_name=_('Agreement Document')
    )
    
    # Termination/Expiry
    termination_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Termination Date'),
        help_text=_('Actual date lease was terminated')
    )
    termination_reason = models.TextField(
        blank=True,
        verbose_name=_('Termination Reason')
    )
    
    # Additional Terms
    terms_and_conditions = models.TextField(
        blank=True,
        verbose_name=_('Terms & Conditions')
    )
    remarks = models.TextField(
        blank=True,
        verbose_name=_('Remarks')
    )
    
    class Meta:
        verbose_name = _('Property Lease')
        verbose_name_plural = _('Property Leases')
        ordering = ['-lease_start_date', '-created_at']
        indexes = [
            models.Index(fields=['lease_number']),
            models.Index(fields=['property', 'status']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['lease_start_date', 'lease_end_date']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['property', 'status'],
                condition=models.Q(status='ACTIVE'),
                name='unique_active_lease_per_property'
            )
        ]
    
    def __str__(self):
        return f"{self.lease_number} - {self.property.property_code} ({self.tenant.name})"
    
    def save(self, *args, **kwargs):
        """
        Override save to:
        1. Auto-generate lease number if not provided
        2. Validate only one active lease per property
        3. Auto-expire lease if end date passed
        """
        def _generate_lease_number():
            from django.utils import timezone
            year = timezone.now().year
            prefix = f'LEASE-{year}-'
            last_lease = PropertyLease.objects.filter(
                lease_number__startswith=prefix
            ).order_by('-lease_number').values_list('lease_number', flat=True).first()
            last_seq = int(last_lease.split('-')[-1]) if last_lease else 0
            return f'{prefix}{last_seq + 1:04d}'
        
        # Auto-generate lease number with retry to avoid race conditions
        if not self.lease_number:
            for attempt in range(5):
                self.lease_number = _generate_lease_number()
                try:
                    with transaction.atomic():
                        # Check for lease end date and auto-expire
                        if self.lease_end_date and self.status == LeaseStatus.ACTIVE:
                            from django.utils import timezone
                            if self.lease_end_date < timezone.now().date():
                                self.status = LeaseStatus.EXPIRED
                        super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    self.lease_number = None
                    if attempt == 4:
                        raise
            return
        
        # Check for lease end date and auto-expire
        if self.lease_end_date and self.status == LeaseStatus.ACTIVE:
            from django.utils import timezone
            if self.lease_end_date < timezone.now().date():
                self.status = LeaseStatus.EXPIRED
        
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        """Return URL for lease detail page."""
        return reverse('property:lease_detail', kwargs={'pk': self.pk})
    
    @_property
    def is_active(self):
        """Check if lease is currently active."""
        return self.status == LeaseStatus.ACTIVE
    
    @_property
    def is_expired(self):
        """Check if lease has passed end date."""
        if not self.lease_end_date:
            return False
        from django.utils import timezone
        return self.lease_end_date < timezone.now().date()
    
    @_property
    def remaining_days(self):
        """Calculate days remaining until lease expires."""
        if not self.lease_end_date:
            return None
        from django.utils import timezone
        delta = self.lease_end_date - timezone.now().date()
        return delta.days if delta.days > 0 else 0
    
    @_property
    def lease_duration_months(self):
        """Calculate total lease duration in months."""
        if not self.lease_end_date:
            return None
        from dateutil.relativedelta import relativedelta
        delta = relativedelta(self.lease_end_date, self.lease_start_date)
        return delta.years * 12 + delta.months
    
    def terminate(self, termination_date=None, reason=''):
        """Terminate this lease."""
        from django.utils import timezone
        self.status = LeaseStatus.TERMINATED
        self.termination_date = termination_date or timezone.now().date()
        self.termination_reason = reason
        self.save()
    
    def renew(self, new_start_date, new_end_date=None, new_rent=None):
        """
        Create a new lease as renewal of this one.
        
        Returns:
            PropertyLease: New lease object
        """
        # Mark current as renewed
        self.status = LeaseStatus.RENEWED
        self.save()
        
        # Create new lease
        new_lease = PropertyLease.objects.create(
            property=self.property,
            tenant=self.tenant,
            lease_start_date=new_start_date,
            lease_end_date=new_end_date,
            monthly_rent=new_rent or self.monthly_rent,
            security_deposit=self.security_deposit,
            annual_increment_percentage=self.annual_increment_percentage,
            status=LeaseStatus.ACTIVE,
            organization=self.organization,
            created_by=self.created_by,
            terms_and_conditions=self.terms_and_conditions
        )
        return new_lease


# ============================================================================
# SUPPORTING MODELS
# ============================================================================

class PropertyPhoto(TimeStampedMixin):
    """
    Property photos/images.
    
    Stores photos of properties for documentation.
    """
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='photos',
        verbose_name=_('Property')
    )
    photo = models.ImageField(
        upload_to='property_photos/%Y/%m/',
        verbose_name=_('Photo')
    )
    caption = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Caption')
    )
    photo_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_('Photo URL'),
        help_text=_('Google Drive or external photo URL')
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name=_('Primary Photo')
    )
    
    class Meta:
        verbose_name = _('Property Photo')
        verbose_name_plural = _('Property Photos')
        ordering = ['-is_primary', '-created_at']
    
    def __str__(self):
        return f"Photo for {self.property.property_code}"


class PropertyDocument(TimeStampedMixin):
    """
    Property documents (rent agreements, contracts, etc.).
    """
    
    DOCUMENT_TYPE_CHOICES = [
        ('LEASE_AGREEMENT', _('Lease Agreement')),
        ('RENT_AGREEMENT', _('Rent Agreement')),
        ('OWNERSHIP_DEED', _('Ownership Deed')),
        ('TRANSFER_DEED', _('Transfer Deed')),
        ('ALLOTMENT_LETTER', _('Allotment Letter')),
        ('SURVEY_REPORT', _('Survey Report')),
        ('VALUATION_REPORT', _('Valuation Report')),
        ('TAX_RECORD', _('Tax Record')),
        ('COURT_ORDER', _('Court Order')),
        ('LEGAL_NOTICE', _('Legal Notice')),
        ('MAINTENANCE_RECORD', _('Maintenance Record')),
        ('INSURANCE_POLICY', _('Insurance Policy')),
        ('OTHER', _('Other Document')),
    ]
    
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name=_('Property')
    )
    document_type = models.CharField(
        max_length=100,
        choices=DOCUMENT_TYPE_CHOICES,
        verbose_name=_('Document Type')
    )
    document = models.FileField(
        upload_to='property_docs/%Y/%m/',
        verbose_name=_('Document')
    )
    document_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_('Document URL'),
        help_text=_('Google Drive or external document URL')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    
    class Meta:
        verbose_name = _('Property Document')
        verbose_name_plural = _('Property Documents')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.document_type} - {self.property.property_code}"


class PropertyHistory(TimeStampedMixin):
    """
    Property audit trail / history log.
    
    Tracks all changes made to property records.
    """
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name=_('Property')
    )
    action = models.CharField(
        max_length=50,
        verbose_name=_('Action'),
        help_text=_('e.g., Created, Updated, Status Changed')
    )
    field_changed = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Field Changed')
    )
    old_value = models.TextField(
        blank=True,
        verbose_name=_('Old Value')
    )
    new_value = models.TextField(
        blank=True,
        verbose_name=_('New Value')
    )
    remarks = models.TextField(
        blank=True,
        verbose_name=_('Remarks')
    )
    changed_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='property_changes',
        verbose_name=_('Changed By')
    )
    
    class Meta:
        verbose_name = _('Property History')
        verbose_name_plural = _('Property History')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.action} - {self.property.property_code} at {self.created_at}"

