"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Forms for Property Management System
-------------------------------------------------------------------------
"""
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from decimal import Decimal

from .models import (
    Mauza, Village, Property, PropertyLease,
    PropertyPhoto, PropertyDocument,
    PropertyType, PropertySubType, PropertyStatus, CourtCaseStatus, LeaseStatus
)
from apps.core.models import District


# District is managed in core app, no form needed here


class MauzaForm(forms.ModelForm):
    """Form for Revenue Estate (Mauza)"""
    
    class Meta:
        model = Mauza
        fields = ['district', 'name', 'code']
        widgets = {
            'district': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter mauza name'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Mauza code (optional)'
            }),
        }


class VillageForm(forms.ModelForm):
    """Form for Village/Neighbourhood"""
    
    class Meta:
        model = Village
        fields = ['mauza', 'name', 'code']
        widgets = {
            'mauza': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter village name'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Village code (optional)'
            }),
        }


class PropertyForm(forms.ModelForm):
    """Form for Property CRUD operations with role-based geographic filtering"""
    
    class Meta:
        model = Property
        fields = [
            # Location
            'district', 'mauza', 'village', 'property_code', 'name', 'address',
            'latitude', 'longitude',
            # Property Details
            'property_type', 'property_sub_type', 'area_marlas',
            'ownership_title', 'survey_number', 'acquisition_date', 'acquisition_cost',
            # Financial
            'current_market_value', 'last_valuation_date',
            'annual_rent', 'last_rent_revision', 'status',
            # Litigation
            'court_case_status', 'court_case_title', 'court_name', 'case_number',
            'next_hearing_date',
            # Additional
            'future_use', 'remarks'
        ]
        widgets = {
            # Location fields
            'district': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_district',
                'required': True
            }),
            'mauza': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_mauza',
                'required': True
            }),
            'village': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_village'
            }),
            'property_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'PES-M001-P001',
                'required': True
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Shop No. 1-A, House 123',
                'required': True
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Complete address',
                'required': True
            }),
            'latitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '34.0082744',
                'step': '0.0000001',
                'required': True
            }),
            'longitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '71.5731692',
                'step': '0.0000001',
                'required': True
            }),
            
            # Property Details
            'property_type': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_property_type',
                'required': True
            }),
            'property_sub_type': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_property_sub_type',
                'required': True
            }),
            'area_marlas': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '10.0000',
                'step': '0.0001',
                'required': True
            }),
            'ownership_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'TMA Peshawar',
                'required': True
            }),
            'survey_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Survey/Khasra number (optional)'
            }),
            'acquisition_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'acquisition_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            
            # Financial
            'current_market_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'last_valuation_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'annual_rent': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '120000.00 (Monthly rent will be auto-calculated)',
                'step': '0.01'
            }),
            'last_rent_revision': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            
            # Litigation
            'court_case_status': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_court_case_status',
                'required': True
            }),
            'court_case_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Case title/description'
            }),
            'court_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Name of court'
            }),
            'case_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Case number'
            }),
            'next_hearing_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            
            # Additional
            'future_use': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Future use or plans'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes or remarks'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        # Extract user for role-based filtering
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Role-based geographic filtering
        if self.user:
            org = self.user.organization
            
            # TMA users: Remove district field entirely (tehsil organization has fixed district)
            if org and org.is_tma() and org.tehsil:
                district = org.tehsil.district
                # Remove district field from form
                del self.fields['district']
                # Store district for later use
                self._tma_district = district
                
                # Initialize mauza queryset based on TMA's district
                self.fields['mauza'].queryset = Mauza.objects.filter(
                    district=district
                ).order_by('name')
                
                # If existing instance, populate village queryset
                if self.instance.pk and self.instance.mauza:
                    self.fields['village'].queryset = Village.objects.filter(
                        mauza=self.instance.mauza
                    ).order_by('name')
                else:
                    self.fields['village'].queryset = Village.objects.none()
            else:
                # Provincial users (LG Department, LCB): See all districts
                self.fields['district'].queryset = District.objects.filter(is_active=True).select_related('division')
                
                # Initialize cascading dropdowns for mauza (based on district)
                if 'district' in self.data:
                    try:
                        district_id = int(self.data.get('district'))
                        self.fields['mauza'].queryset = Mauza.objects.filter(district_id=district_id).order_by('name')
                    except (ValueError, TypeError):
                        self.fields['mauza'].queryset = Mauza.objects.none()
                elif self.instance.pk:
                    self.fields['mauza'].queryset = Mauza.objects.filter(district=self.instance.district).order_by('name')
                else:
                    # Default: show mauzas for initial district (if set)
                    if self.fields['district'].initial:
                        self.fields['mauza'].queryset = Mauza.objects.filter(district=self.fields['district'].initial).order_by('name')
                    else:
                        self.fields['mauza'].queryset = Mauza.objects.none()
                
                # Initialize cascading dropdowns for village (based on mauza)
                if 'mauza' in self.data:
                    try:
                        mauza_id = int(self.data.get('mauza'))
                        self.fields['village'].queryset = Village.objects.filter(mauza_id=mauza_id).order_by('name')
                    except (ValueError, TypeError):
                        self.fields['village'].queryset = Village.objects.none()
                elif self.instance.pk and self.instance.mauza:
                    self.fields['village'].queryset = Village.objects.filter(mauza=self.instance.mauza).order_by('name')
                else:
                    self.fields['village'].queryset = Village.objects.none()
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        annual_rent = cleaned_data.get('annual_rent')
        
        # Validate financial fields for rented properties
        if status == PropertyStatus.RENTED_OUT:
            if not annual_rent or annual_rent <= 0:
                raise ValidationError('Annual rent must be greater than 0 for rented property.')
        
        # Validate litigation fields
        court_case_status = cleaned_data.get('court_case_status')
        case_number = cleaned_data.get('case_number')
        
        if court_case_status != CourtCaseStatus.NO_CASE and not case_number:
            raise ValidationError('Case number is required when property has a court case.')
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # For TMA users: automatically set district from their tehsil
        if hasattr(self, '_tma_district'):
            instance.district = self._tma_district
        
        if commit:
            instance.save()
        return instance


class PropertyLeaseForm(forms.ModelForm):
    """Form for creating/editing property leases"""
    
    class Meta:
        model = PropertyLease
        fields = [
            'property', 'tenant', 'lease_start_date', 'lease_end_date',
            'monthly_rent', 'security_deposit', 'annual_increment_percentage',
            'status', 'agreement_date', 'agreement_document',
            'terms_and_conditions', 'remarks'
        ]
        widgets = {
            'property': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'tenant': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'lease_start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True
            }),
            'lease_end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'Leave blank for month-to-month'
            }),
            'monthly_rent': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '10000.00',
                'step': '0.01',
                'required': True
            }),
            'security_deposit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'annual_increment_percentage': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '10.00',
                'step': '0.01'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'agreement_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'agreement_document': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx'
            }),
            'terms_and_conditions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Terms and conditions of the lease'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional remarks'
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        lease_start = cleaned_data.get('lease_start_date')
        lease_end = cleaned_data.get('lease_end_date')
        property_obj = cleaned_data.get('property')
        status = cleaned_data.get('status')
        
        # Validate date range
        if lease_start and lease_end and lease_end <= lease_start:
            raise ValidationError('Lease end date must be after start date.')
        
        # Check for overlapping active leases
        if property_obj and status == 'ACTIVE':
            existing_active = PropertyLease.objects.filter(
                property=property_obj,
                status='ACTIVE'
            )
            if self.instance.pk:
                existing_active = existing_active.exclude(pk=self.instance.pk)
            
            if existing_active.exists():
                raise ValidationError(
                    f'Property {property_obj.property_code} already has an active lease.'
                )
        
        return cleaned_data


class PropertyPhotoForm(forms.ModelForm):
    """Form for uploading property photos"""
    
    class Meta:
        model = PropertyPhoto
        fields = ['photo', 'caption', 'is_primary']
        widgets = {
            'photo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'caption': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Photo caption/description'
            }),
            'is_primary': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }


class PropertyDocumentForm(forms.ModelForm):
    """Form for uploading property documents"""
    
    class Meta:
        model = PropertyDocument
        fields = ['document_type', 'document', 'description']
        widgets = {
            'document_type': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'document': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Document description'
            }),
        }


class PropertyFilterForm(forms.Form):
    """Form for filtering property list with role-based hierarchical filtering"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by code, address, or tenant name...'
        })
    )
    
    # Hierarchical geographic filters (for provincial users)
    division = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label='All Divisions',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_filter_division'
        })
    )
    
    district = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label='All Districts',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_filter_district'
        })
    )
    
    tehsil = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label='All Tehsils',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_filter_tehsil'
        })
    )
    
    mauza = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label='All Mauzas',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_filter_mauza'
        })
    )
    
    village = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label='All Villages',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_filter_village'
        })
    )
    
    property_type = forms.ChoiceField(
        choices=[('', 'All Types')] + PropertyType.choices,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + PropertyStatus.choices,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    is_rented = forms.ChoiceField(
        choices=[
            ('', 'All'),
            ('yes', 'Rented Only'),
            ('no', 'Vacant Only')
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    has_litigation = forms.ChoiceField(
        choices=[
            ('', 'All'),
            ('yes', 'With Litigation'),
            ('no', 'Without Litigation')
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        from apps.core.models import Division, Tehsil
        
        # Superusers get full access to all filters
        if user and user.is_superuser:
            self.fields['division'].queryset = Division.objects.filter(
                is_active=True
            ).order_by('name')
            
            self.fields['district'].queryset = District.objects.filter(
                is_active=True
            ).select_related('division').order_by('division__name', 'name')
            
            self.fields['tehsil'].queryset = Tehsil.objects.filter(
                is_active=True
            ).select_related('district__division').order_by('district__division__name', 'district__name', 'name')
            
            self.fields['mauza'].queryset = Mauza.objects.select_related(
                'district__division'
            ).order_by('district__division__name', 'district__name', 'name')
            
            self.fields['village'].queryset = Village.objects.select_related(
                'mauza__district__division'
            ).order_by('mauza__district__division__name', 'mauza__district__name', 'mauza__name', 'name')
        
        elif user and user.organization:
            org = user.organization
            
            # TMA users: Only see their district/tehsil/mauza hierarchy
            if org.is_tma() and org.tehsil:
                # Hide division, district, tehsil (they're fixed)
                del self.fields['division']
                del self.fields['district']
                del self.fields['tehsil']
                
                # Show only mauzas in their district
                self.fields['mauza'].queryset = Mauza.objects.filter(
                    district=org.tehsil.district
                ).order_by('name')
                
                # Villages will be populated via AJAX based on mauza
                self.fields['village'].queryset = Village.objects.filter(
                    mauza__district=org.tehsil.district
                ).order_by('name')
            else:
                # Provincial users (LG Department, LCB): Full hierarchical access
                from apps.core.models import Division, Tehsil
                
                self.fields['division'].queryset = Division.objects.filter(
                    is_active=True
                ).order_by('name')
                
                self.fields['district'].queryset = District.objects.filter(
                    is_active=True
                ).select_related('division').order_by('division__name', 'name')
                
                self.fields['tehsil'].queryset = Tehsil.objects.filter(
                    is_active=True
                ).select_related('district__division').order_by('district__division__name', 'district__name', 'name')
                
                self.fields['mauza'].queryset = Mauza.objects.select_related(
                    'district__division'
                ).order_by('district__division__name', 'district__name', 'name')
                
                self.fields['village'].queryset = Village.objects.select_related(
                    'mauza__district__division'
                ).order_by('mauza__district__division__name', 'mauza__district__name', 'mauza__name', 'name')
        else:
            # No user context or no organization - hide geographic filters
            del self.fields['division']
            del self.fields['district']
            del self.fields['tehsil']
            self.fields['mauza'].queryset = Mauza.objects.none()
            self.fields['village'].queryset = Village.objects.none()
            self.fields['village'].queryset = Village.objects.none()


# Inline formsets for photos and documents
PropertyPhotoFormSet = inlineformset_factory(
    Property,
    PropertyPhoto,
    form=PropertyPhotoForm,
    extra=1,
    can_delete=True,
    max_num=10
)

PropertyDocumentFormSet = inlineformset_factory(
    Property,
    PropertyDocument,
    form=PropertyDocumentForm,
    extra=1,
    can_delete=True,
    max_num=15
)
