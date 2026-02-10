"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Property Management views
-------------------------------------------------------------------------
"""
from django.views.generic import (
    TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView, View
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect, render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count, Sum
from django.contrib import messages
from django.db import transaction
from typing import Dict, Any
from decimal import Decimal
import csv
import io
import re
import logging

logger = logging.getLogger(__name__)

from .models import (
    Mauza, Village, Property, PropertyLease, PropertyHistory,
    PropertyStatus, CourtCaseStatus, LeaseStatus, PropertyType
)
from apps.core.models import District, Division, Tehsil, Organization
from .forms import (
    PropertyForm, PropertyFilterForm, PropertyLeaseForm, MauzaForm, VillageForm,
    PropertyPhotoFormSet, PropertyDocumentFormSet
)


class PropertyDashboardView(LoginRequiredMixin, TemplateView):
    """Main dashboard for Property Management (GIS) module."""
    
    template_name = 'property/dashboard.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        
        # Role-based property queryset
        user = self.request.user
        org = user.organization
        
        if org and org.is_tma():
            # TMA users: See only their organization's properties
            properties = Property.objects.filter(organization=org)
        else:
            # Provincial users (LG Department, LCB): See all properties
            properties = Property.objects.all()
        
        context.update({
            'page_title': 'Immoveable Property Management (GIS)',
            'module_name': 'Property Management',
            'total_properties': properties.count(),
            'rented_properties': properties.filter(status=PropertyStatus.RENTED_OUT).count(),
            'vacant_properties': properties.filter(status=PropertyStatus.VACANT).count(),
            'litigation_properties': properties.exclude(court_case_status=CourtCaseStatus.NO_CASE).count(),
            'total_area_marlas': properties.aggregate(Sum('area_marlas'))['area_marlas__sum'] or Decimal('0'),
            'total_annual_rent': properties.filter(status=PropertyStatus.RENTED_OUT).aggregate(
                Sum('annual_rent')
            )['annual_rent__sum'] or Decimal('0'),
        })
        
        # Calculate derived values
        total_area = context['total_area_marlas']
        context['total_area_sqft'] = total_area * Decimal('225')  # 1 Marla = 225 sq.ft
        context['total_area_sqm'] = total_area * Decimal('20.9')  # 1 Marla = 20.9 sq.m
        
        total_annual = context['total_annual_rent']
        context['total_monthly_rent'] = total_annual / Decimal('12') if total_annual else Decimal('0')
        
        return context


class PropertyListView(LoginRequiredMixin, ListView):
    """List view for properties with hierarchical search and filters."""
    
    model = Property
    template_name = 'property/property_list.html'
    context_object_name = 'properties'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        org = user.organization if hasattr(user, 'organization') else None
        
        # Role-based base queryset
        if user.is_superuser:
            # Superusers: See all properties across all organizations
            queryset = Property.objects.all()
        elif org and org.is_tma():
            # TMA users: See only their organization's properties
            queryset = Property.objects.filter(organization=org)
        else:
            # Provincial users (LG Department, LCB): See all properties
            queryset = Property.objects.all()
        
        queryset = queryset.select_related(
            'district', 'mauza', 'village', 'organization'
        ).prefetch_related(
            'leases'
        ).order_by('-created_at')
        
        # Apply search filter
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(property_code__icontains=search) |
                Q(address__icontains=search) |
                Q(ownership_title__icontains=search)
            )
        
        # Hierarchical geographic filters (for provincial users)
        division = self.request.GET.get('division')
        if division:
            queryset = queryset.filter(district__division_id=division)
        
        # Apply filter form filters
        district_id = self.request.GET.get('district')
        if district_id:
            queryset = queryset.filter(district_id=district_id)
        
        tehsil = self.request.GET.get('tehsil')
        if tehsil:
            queryset = queryset.filter(district__tehsils__id=tehsil)
        
        mauza_id = self.request.GET.get('mauza')
        if mauza_id:
            queryset = queryset.filter(mauza_id=mauza_id)
        
        village_id = self.request.GET.get('village')
        if village_id:
            queryset = queryset.filter(village_id=village_id)
        
        property_type = self.request.GET.get('property_type')
        if property_type:
            queryset = queryset.filter(property_type=property_type)
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        is_rented = self.request.GET.get('is_rented')
        if is_rented == 'yes':
            queryset = queryset.filter(status=PropertyStatus.RENTED_OUT)
        elif is_rented == 'no':
            queryset = queryset.exclude(status=PropertyStatus.RENTED_OUT)
        
        has_litigation = self.request.GET.get('has_litigation')
        if has_litigation == 'yes':
            queryset = queryset.exclude(court_case_status=CourtCaseStatus.NO_CASE)
        elif has_litigation == 'no':
            queryset = queryset.filter(court_case_status=CourtCaseStatus.NO_CASE)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = PropertyFilterForm(self.request.GET, user=self.request.user)
        context['page_title'] = 'Property List'
        return context


class PropertyDetailView(LoginRequiredMixin, DetailView):
    """Detail view for a single property with photos and documents."""
    
    model = Property
    template_name = 'property/property_detail.html'
    context_object_name = 'property'
    
    def get_queryset(self):
        user = self.request.user
        
        if user.is_superuser:
            # Superusers can view all properties
            queryset = Property.objects.all()
        else:
            # Regular users see only their organization's properties
            queryset = Property.objects.filter(organization=user.organization)
        
        return queryset.select_related(
            'district', 'mauza', 'village', 'organization'
        ).prefetch_related(
            'leases', 'photos', 'documents', 'history'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Property: {self.object.property_code}'
        context['photos'] = self.object.photos.all().order_by('-is_primary', '-created_at')
        context['documents'] = self.object.documents.all().order_by('-created_at')
        context['history'] = self.object.history.all().order_by('-created_at')[:10]
        return context


class PropertyCreateView(LoginRequiredMixin, CreateView):
    """Create view for adding new property."""
    
    model = Property
    form_class = PropertyForm
    template_name = 'property/property_form.html'
    success_url = reverse_lazy('property:list')
    
    def get_form_kwargs(self):
        """Pass user to form for role-based filtering"""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Add New Property'
        context['form_action'] = 'Create'
        if self.request.POST:
            context['photo_formset'] = PropertyPhotoFormSet(self.request.POST, self.request.FILES)
            context['document_formset'] = PropertyDocumentFormSet(self.request.POST, self.request.FILES)
        else:
            context['photo_formset'] = PropertyPhotoFormSet()
            context['document_formset'] = PropertyDocumentFormSet()
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        photo_formset = context['photo_formset']
        document_formset = context['document_formset']
        
        form.instance.organization = self.request.user.organization
        form.instance.created_by = self.request.user
        
        if photo_formset.is_valid() and document_formset.is_valid():
            self.object = form.save()
            photo_formset.instance = self.object
            document_formset.instance = self.object
            photo_formset.save()
            document_formset.save()
            
            # Log property creation
            PropertyHistory.objects.create(
                property=self.object,
                action='CREATED',
                changed_by=self.request.user,
                remarks=f'Property {self.object.property_code} created'
            )
            
            messages.success(
                self.request,
                f'Property {self.object.property_code} created successfully!'
            )
            return redirect(self.success_url)
        else:
            return self.form_invalid(form)


class PropertyUpdateView(LoginRequiredMixin, UpdateView):
    """Update view for editing existing property."""
    
    model = Property
    form_class = PropertyForm
    template_name = 'property/property_form.html'
    
    def get_queryset(self):
        user = self.request.user
        
        if user.is_superuser:
            # Superusers can edit all properties
            return Property.objects.all()
        else:
            # Regular users can only edit their organization's properties
            return Property.objects.filter(organization=user.organization)
    
    def get_form_kwargs(self):
        """Pass user to form for role-based filtering"""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_success_url(self):
        return reverse_lazy('property:detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        context = self.get_context_data()
        photo_formset = context['photo_formset']
        document_formset = context['document_formset']
        
        # Track changes for audit
        changed_fields = []
        for field in form.changed_data:
            old_value = getattr(self.object, field, None)
            new_value = form.cleaned_data.get(field)
            changed_fields.append(f'{field}: {old_value} -> {new_value}')
        
        if photo_formset.is_valid() and document_formset.is_valid():
            self.object = form.save()
            photo_formset.instance = self.object
            document_formset.instance = self.object
            photo_formset.save()
            document_formset.save()
            
            # Log property update
            if changed_fields:
                PropertyHistory.objects.create(
                    property=self.object,
                    action='UPDATED',
                    changed_by=self.request.user,
                    field_changed=', '.join(form.changed_data),
                    remarks=f'Updated fields: {", ".join(changed_fields)}'
                )
            
            messages.success(
                self.request,
                f'Property {self.object.property_code} updated successfully!'
            )
            return redirect(self.get_success_url())
        else:
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Edit Property: {self.object.property_code}'
        context['form_action'] = 'Update'
        
        if self.request.POST:
            context['photo_formset'] = PropertyPhotoFormSet(self.request.POST, self.request.FILES, instance=self.object)
            context['document_formset'] = PropertyDocumentFormSet(self.request.POST, self.request.FILES, instance=self.object)
        else:
            context['photo_formset'] = PropertyPhotoFormSet(instance=self.object)
            context['document_formset'] = PropertyDocumentFormSet(instance=self.object)
        
        return context


class PropertyDeleteView(LoginRequiredMixin, DeleteView):
    """Delete view for removing property."""
    
    model = Property
    template_name = 'property/property_confirm_delete.html'
    success_url = reverse_lazy('property:list')
    
    def get_queryset(self):
        user = self.request.user
        
        if user.is_superuser:
            # Superusers can delete all properties
            return Property.objects.all()
        else:
            # Regular users can only delete their organization's properties
            return Property.objects.filter(organization=user.organization)
    
    def delete(self, request, *args, **kwargs):
        property_code = self.get_object().property_code
        response = super().delete(request, *args, **kwargs)
        messages.success(
            request,
            f'Property {property_code} deleted successfully!'
        )
        return response


# AJAX Views for Cascading Dropdowns

def load_mauzas(request):
    """AJAX endpoint to load mauzas based on selected district."""
    district_id = request.GET.get('district_id')
    mauzas = Mauza.objects.filter(district_id=district_id).order_by('name')
    return JsonResponse({
        'mauzas': list(mauzas.values('id', 'name'))
    })


def load_villages(request):
    """AJAX endpoint to load villages based on selected mauza."""
    mauza_id = request.GET.get('mauza_id')
    villages = Village.objects.filter(mauza_id=mauza_id).order_by('name')
    return JsonResponse({
        'villages': list(villages.values('id', 'name'))
    })


def load_districts(request):
    """AJAX endpoint to load districts based on selected division."""
    division_id = request.GET.get('division_id')
    districts = District.objects.filter(division_id=division_id).order_by('name')
    return JsonResponse({
        'districts': list(districts.values('id', 'name'))
    })


def load_tehsils(request):
    """AJAX endpoint to load tehsils based on selected district."""
    district_id = request.GET.get('district_id')
    tehsils = Tehsil.objects.filter(district_id=district_id).order_by('name')
    return JsonResponse({
        'tehsils': list(tehsils.values('id', 'name'))
    })


# Master Data Views (Optional - can also use admin interface)

class DistrictListView(LoginRequiredMixin, ListView):
    """List view for districts."""
    model = District
    template_name = 'property/district_list.html'
    context_object_name = 'districts'
    paginate_by = 20


class MauzaListView(LoginRequiredMixin, ListView):
    """List view for mauzas."""
    model = Mauza
    template_name = 'property/mauza_list.html'
    context_object_name = 'mauzas'
    paginate_by = 20
    
    def get_queryset(self):
        return Mauza.objects.select_related('district').order_by('district__name', 'name')


class VillageListView(LoginRequiredMixin, ListView):
    """List view for villages."""
    model = Village
    template_name = 'property/village_list.html'
    context_object_name = 'villages'
    paginate_by = 20
    
    def get_queryset(self):
        return Village.objects.select_related('mauza__district').order_by('mauza__name', 'name')

# ============================================================================
# PROPERTY LEASE VIEWS
# ============================================================================

class PropertyLeaseListView(LoginRequiredMixin, ListView):
    """List view for property leases."""
    model = PropertyLease
    template_name = 'property/lease_list.html'
    context_object_name = 'leases'
    paginate_by = 20
    
    def get_queryset(self):
        return PropertyLease.objects.filter(
            organization=self.request.user.organization
        ).select_related('property', 'tenant').order_by('-created_at')


class PropertyLeaseDetailView(LoginRequiredMixin, DetailView):
    """Detail view for a property lease."""
    model = PropertyLease
    template_name = 'property/lease_detail.html'
    context_object_name = 'lease'
    
    def get_queryset(self):
        return PropertyLease.objects.filter(
            organization=self.request.user.organization
        ).select_related('property', 'tenant')


class PropertyLeaseCreateView(LoginRequiredMixin, CreateView):
    """Create view for new property lease."""
    model = PropertyLease
    form_class = PropertyLeaseForm
    template_name = 'property/lease_form.html'
    success_url = reverse_lazy('property:lease_list')
    
    def get_initial(self):
        """Pre-select property if passed in URL parameter."""
        initial = super().get_initial()
        property_id = self.request.GET.get('property')
        if property_id:
            try:
                property_obj = Property.objects.get(pk=property_id)
                initial['property'] = property_obj
            except Property.DoesNotExist:
                pass
        return initial
    
    def form_valid(self, form):
        form.instance.organization = self.request.user.organization
        form.instance.created_by = self.request.user
        
        # Update property status to rented if lease is active
        if form.instance.status == LeaseStatus.ACTIVE:
            property_obj = form.instance.property
            property_obj.status = PropertyStatus.RENTED_OUT
            property_obj.save()
        
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Lease {self.object.lease_number} created successfully!'
        )
        return response
    
    def get_success_url(self):
        """Return to property detail page if coming from there."""
        return_to_property = self.request.GET.get('property')
        if return_to_property:
            return reverse_lazy('property:detail', kwargs={'pk': return_to_property})
        return reverse_lazy('property:lease_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = 'Create'
        return context


class PropertyLeaseUpdateView(LoginRequiredMixin, UpdateView):
    """Update view for existing lease."""
    model = PropertyLease
    form_class = PropertyLeaseForm
    template_name = 'property/lease_form.html'
    success_url = reverse_lazy('property:lease_list')
    
    def get_queryset(self):
        return PropertyLease.objects.filter(
            organization=self.request.user.organization
        )
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Lease {self.object.lease_number} updated successfully!'
        )
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = 'Update'
        return context


class PropertyLeaseTerminateView(LoginRequiredMixin, TemplateView):
    """View to terminate a lease."""
    template_name = 'property/lease_terminate.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_superuser:
            lease = get_object_or_404(PropertyLease, pk=kwargs['pk'])
        else:
            lease = get_object_or_404(
                PropertyLease,
                pk=kwargs['pk'],
                organization=user.organization
            )
        context['lease'] = lease
        return context
    
    def post(self, request, *args, **kwargs):
        from django.utils import timezone
        
        user = request.user
        if user.is_superuser:
            lease = get_object_or_404(PropertyLease, pk=kwargs['pk'])
        else:
            lease = get_object_or_404(
                PropertyLease,
                pk=kwargs['pk'],
                organization=user.organization
            )
        termination_reason = request.POST.get('termination_reason', '')
        
        lease.terminate(
            termination_date=timezone.now().date(),
            reason=termination_reason
        )
        
        # Update property status to vacant
        property_obj = lease.property
        property_obj.status = PropertyStatus.VACANT
        property_obj.save()
        
        messages.success(
            request,
            f'Lease {lease.lease_number} terminated successfully!'
        )
        return redirect('property:lease_list')


class PropertyCSVImportView(LoginRequiredMixin, TemplateView):
    """
    Bulk import properties from CSV file with comprehensive validation.
    
    Expected CSV columns:
    - S No
    - Office Name
    - District Name
    - Name of Property
    - Complete Address
    - Google Coordinates (Exact Latitude and Longitude)
    - Property Type
    - Property Details / Current use
    - Total Area (in Marlas)
    - Ownership title as per land revenue record
    - Name of Mauza / Revenue estate
    - Name of Village / Neighbourhood Council
    - Property Status
    - Annual Rent 2025-26
    - Court case with title
    - Name of Court
    - Future use of the property as planned by your organization (if any)
    - Other details / Remarks
    - Relevant photos
    """
    template_name = 'property/property_csv_import.html'
    
    def get(self, request):
        return render(request, self.template_name)
    
    def post(self, request):
        csv_file = request.FILES.get('csv_file')
        
        if not csv_file:
            messages.error(request, 'Please upload a CSV file.')
            return redirect('property:csv_import')
        
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a valid CSV file.')
            return redirect('property:csv_import')
        
        # Parse CSV
        try:
            decoded_file = csv_file.read().decode('utf-8-sig').splitlines()
        except UnicodeDecodeError:
            try:
                csv_file.seek(0)
                decoded_file = csv_file.read().decode('latin-1').splitlines()
            except:
                messages.error(request, 'File encoding error. Please ensure UTF-8 or Latin-1 encoding.')
                return redirect('property:csv_import')
        
        reader = csv.DictReader(decoded_file)
        
        # Validation phase - collect all errors before processing
        errors = []
        warnings = []
        validated_rows = []
        row_num = 1  # Header row
        
        # Cache for lookups to avoid repeated queries
        org_cache = {}
        district_cache = {}
        mauza_cache = {}
        village_cache = {}
        
        for row in reader:
            row_num += 1
            row_errors = []
            row_warnings = []
            
            try:
                # Extract and clean data
                s_no = row.get('S No', '').strip()
                office_name = row.get('Office Name', '').strip()
                district_name = row.get('District Name', '').strip()
                property_name = row.get('Name of Property', '').strip()
                address = row.get('Complete Address', '').strip()
                coordinates = row.get('Google Coordinates (Exact Latitude and Longitude)', '').strip()
                property_type_str = row.get('Property Type', '').strip()
                property_details = row.get('Property Details / Current use', '').strip()
                area_str = row.get('Total Area (in Marlas)', '').strip()
                ownership_title = row.get('Ownership title as per land revenue record', '').strip()
                mauza_name = row.get('Name of Mauza / Revenue estate', '').strip()
                village_name = row.get('Name of Village / Neighbourhood Council', '').strip()
                property_status_str = row.get('Property Status', '').strip()
                annual_rent_str = row.get('Annual Rent 2025-26', '').strip()
                court_case_title = row.get('Court case with title', '').strip()
                court_name = row.get('Name of Court', '').strip()
                future_use = row.get('Future use of the property as planned by your organization (if any)', '').strip()
                remarks = row.get('Other details / Remarks', '').strip()
                photo_url = row.get('Relevant photos', '').strip()
                
                # Validate required fields
                if not office_name:
                    row_errors.append('Office Name is required')
                
                if not district_name:
                    row_errors.append('District Name is required')
                
                if not property_name:
                    row_errors.append('Name of Property is required')
                
                if not address:
                    row_errors.append('Complete Address is required')
                
                if not mauza_name:
                    row_errors.append('Name of Mauza is required')
           
                # Lookup Organization
                organization = None
                if office_name:
                    if office_name not in org_cache:
                        orgs = Organization.objects.filter(
                            Q(name__iexact=office_name) |
                            Q(name__icontains=office_name)
                        )
                        if orgs.count() == 1:
                            org_cache[office_name] = orgs.first()
                        elif orgs.count() > 1:
                            row_warnings.append(f'Multiple organizations found for "{office_name}", using first match: {orgs.first().name}')
                            org_cache[office_name] = orgs.first()
                        else:
                            org_cache[office_name] = None
                    
                    organization = org_cache[office_name]
                    if not organization:
                        row_errors.append(f'Organization "{office_name}" not found')
                
                # Lookup District
                district = None
                if district_name:
                    if district_name not in district_cache:
                        districts = District.objects.filter(name__iexact=district_name)
                        if districts.exists():
                            district_cache[district_name] = districts.first()
                        else:
                            district_cache[district_name] = None
                    
                    district = district_cache[district_name]
                    if not district:
                        row_errors.append(f'District "{district_name}" not found')
                
                # Lookup or Create Mauza
                mauza = None
                if mauza_name and district:
                    cache_key = f'{district_name}_{mauza_name}'
                    if cache_key not in mauza_cache:
                        mauzas = Mauza.objects.filter(
                            name__iexact=mauza_name,
                            district=district
                        )
                        if mauzas.exists():
                            mauza_cache[cache_key] = mauzas.first()
                        else:
                            # Auto-create Mauza if it doesn't exist
                            mauza_cache[cache_key] = Mauza.objects.create(
                                name=mauza_name,
                                district=district
                            )
                            row_warnings.append(f'Created new Mauza: "{mauza_name}" in {district_name}')
                    
                    mauza = mauza_cache[cache_key]
                
                # Lookup or Create Village (optional)
                village = None
                if village_name and mauza:
                    cache_key = f'{district_name}_{mauza_name}_{village_name}'
                    if cache_key not in village_cache:
                        villages = Village.objects.filter(
                            name__iexact=village_name,
                            mauza=mauza
                        )
                        if villages.exists():
                            village_cache[cache_key] = villages.first()
                        else:
                            # Auto-create Village if it doesn't exist
                            village_cache[cache_key] = Village.objects.create(
                                name=village_name,
                                mauza=mauza
                            )
                            row_warnings.append(f'Created new Village: "{village_name}" in {mauza_name}')
                
                # Parse coordinates
                latitude = None
                longitude = None
                if coordinates:
                    # Try parsing "lat,long" format
                    coords = coordinates.replace('"', '').replace(' ', '')
                    match = re.match(r'([-+]?\d+\.\d+),([-+]?\d+\.\d+)', coords)
                    if match:
                        latitude = Decimal(match.group(1))
                        longitude = Decimal(match.group(2))
                    else:
                        row_errors.append(f'Invalid coordinates format: "{coordinates}" (expected: "latitude,longitude")')
                else:
                    row_warnings.append('No coordinates provided')
                
                # Parse property type
                property_type = None
                if property_type_str:
                    property_type_map = {
                        'commercial': PropertyType.COMMERCIAL,
                        'residential': PropertyType.RESIDENTIAL,
                        'agricultural': PropertyType.AGRICULTURAL,
                        'industrial': PropertyType.INDUSTRIAL,
                        'mixed use': PropertyType.MIXED_USE,
                        'mixed': PropertyType.MIXED_USE,
                        'institutional': PropertyType.INSTITUTIONAL,
                        'government': PropertyType.INSTITUTIONAL,
                        'public': PropertyType.INSTITUTIONAL,
                        'official': PropertyType.INSTITUTIONAL,
                        'open plot': PropertyType.RESIDENTIAL,
                        'plot': PropertyType.RESIDENTIAL,
                    }
                    property_type = property_type_map.get(property_type_str.lower())
                    if not property_type:
                        row_errors.append(f'Invalid Property Type: "{property_type_str}"')
                
                # Parse area
                area_marlas = Decimal('0')
                if area_str:
                    try:
                        area_marlas = Decimal(str(area_str))
                        if area_marlas < 0:
                            row_errors.append('Area cannot be negative')
                    except (ValueError, Exception):
                        row_warnings.append(f'Invalid area value: "{area_str}", setting to 0')
                        area_marlas = Decimal('0')
                
                # Parse property status
                property_status = PropertyStatus.VACANT  # Default
                if property_status_str:
                    status_map = {
                        'vacant': PropertyStatus.VACANT,
                        'rented out': PropertyStatus.RENTED_OUT,
                        'rented': PropertyStatus.RENTED_OUT,
                        'self-use': PropertyStatus.SELF_USE,
                        'self use': PropertyStatus.SELF_USE,
                        'under construction': PropertyStatus.UNDER_CONSTRUCTION,
                        'under litigation': PropertyStatus.UNDER_LITIGATION,
                        'litigation': PropertyStatus.UNDER_LITIGATION,
                        'disputed': PropertyStatus.UNDER_LITIGATION,
                        'encroached': PropertyStatus.ENCROACHED,
                        'demolished': PropertyStatus.DEMOLISHED,
                    }
                    property_status = status_map.get(property_status_str.lower(), PropertyStatus.VACANT)
                
                # Parse annual rent
                annual_rent = Decimal('0')
                if annual_rent_str:
                    try:
                        annual_rent = Decimal(annual_rent_str.replace(',', ''))
                    except (ValueError, Exception):
                        row_warnings.append(f'Invalid annual rent value: "{annual_rent_str}", setting to zero')
                        annual_rent = Decimal('0')
                
                # Parse court case status
                court_case_status = CourtCaseStatus.NO_CASE
                case_number = ''
                if court_case_title and court_case_title.lower() not in ['nil', 'none', 'n/a', '']:
                    court_case_status = CourtCaseStatus.PENDING
                    case_number = court_case_title
                
                # Generate property code if not provided
                property_code = property_name
                if s_no:
                    property_code = f'{district_name[:3].upper()}-{s_no}'
                
                # Store validated row if no critical errors
                if not row_errors:
                    validated_rows.append({
                        'property_code': property_code,
                        'name': property_name,
                        'address': address,
                        'latitude': latitude,
                        'longitude': longitude,
                        'property_type': property_type,
                        'property_sub_type': property_type,  # Same as type for now
                        'area_marlas': area_marlas or Decimal('0'),
                        'ownership_title': ownership_title or 'N/A',
                        'status': property_status,
                        'annual_rent': annual_rent or Decimal('0'),
                        'court_case_status': court_case_status,
                        'case_number': case_number,
                        'court_case_title': court_case_title if court_case_status != CourtCaseStatus.NO_CASE else '',
                        'court_name': court_name if court_case_status != CourtCaseStatus.NO_CASE else '',
                        'future_use': future_use,
                        'remarks': remarks,
                        'organization': organization,
                        'district': district,
                        'mauza': mauza,
                        'village': village,
                        'photo_url': photo_url,
                    })
                else:
                    errors.append(f'Row {row_num}: {"; ".join(row_errors)}')
                
                if row_warnings:
                    warnings.append(f'Row {row_num}: {"; ".join(row_warnings)}')
            
            except Exception as e:
                errors.append(f'Row {row_num}: Unexpected error - {str(e)}')
        
        # Display validation results
        if errors:
            messages.error(request, f'Found {len(errors)} error(s) during validation. Please fix and try again.')
            for error in errors[:10]:
                messages.error(request, error)
            if len(errors) > 10:
                messages.error(request, f'... and {len(errors) - 10} more errors.')
            return render(request, self.template_name, {
                'errors': errors,
                'warnings': warnings,
                'error_count': len(errors),
                'warning_count': len(warnings),
            })
        
        # Import phase - create properties in transaction
        try:
            with transaction.atomic():
                created_count = 0
                updated_count = 0
                
                for row_data in validated_rows:
                    property_obj, created = Property.objects.update_or_create(
                        property_code=row_data['property_code'],
                        defaults={
                            'name': row_data['name'],
                            'address': row_data['address'],
                            'latitude': row_data['latitude'],
                            'longitude': row_data['longitude'],
                            'property_type': row_data['property_type'],
                            'property_sub_type': row_data['property_sub_type'],
                            'area_marlas': row_data['area_marlas'],
                            'ownership_title': row_data['ownership_title'],
                            'status': row_data['status'],
                            'annual_rent': row_data['annual_rent'],
                            'court_case_status': row_data['court_case_status'],
                            'case_number': row_data['case_number'],
                            'court_case_title': row_data['court_case_title'],
                            'court_name': row_data['court_name'],
                            'future_use': row_data['future_use'],
                            'remarks': row_data['remarks'],
                            'organization': row_data['organization'],
                            'mauza': row_data['mauza'],
                            'village': row_data['village'],
                        }
                    )
                    
                    if created:
                        created_count += 1
                        # Log creation
                        PropertyHistory.objects.create(
                            property=property_obj,
                            action='CREATED',
                            changed_by=request.user,
                            remarks='Created via CSV import'
                        )
                    else:
                        updated_count += 1
                
                # Success messages
                if created_count > 0:
                    messages.success(request, f'Successfully created {created_count} property/properties.')
                
                if updated_count > 0:
                    messages.info(request, f'Updated {updated_count} existing property/properties.')
                
                if warnings:
                    messages.warning(request, f'{len(warnings)} warning(s) encountered (see below)')
                    for warning in warnings[:10]:
                        messages.warning(request, warning)
                
                return redirect('property:list')
        
        except Exception as e:
            messages.error(request, f'Error saving properties: {str(e)}')
            return redirect('property:csv_import')


class PropertyCSVTemplateView(LoginRequiredMixin, TemplateView):
    """Download CSV template for property import."""
    
    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="property_import_template.csv"'
        
        writer = csv.writer(response)
        # Write header
        writer.writerow([
            'S No',
            'Office Name',
            'District Name',
            'Name of Property',
            'Complete Address',
            'Google Coordinates (Exact Latitude and Longitude)',
            'Property Type',
            'Property Details / Current use',
            'Total Area (in Marlas)',
            'Ownership title as per land revenue record',
            'Name of Mauza / Revenue estate',
            'Name of Village / Neighbourhood Council',
            'Property Status',
            'Annual Rent 2025-26',
            'Court case with title',
            'Name of Court',
            'Future use of the property as planned by your organization (if any)',
            'Other details / Remarks',
            'Relevant photos',
        ])
        
        # Write example row
        writer.writerow([
            '1',
            'Capital Metropolitan Government Peshawar',
            'Peshawar',
            'Shop No.1-A',
            'Chowk Bazazan Kisa Khwani Peshawar City',
            '34.0082744,71.5731692',
            'Commercial',
            'Shop',
            '0.4044',
            'Municipal Corporation Peshawar',
            'Abadai Peshawar',
            'Chowk Nasir Khan CRMS',
            'Rented Out',
            '62136',
            'Nil',
            'Nil',
            'Nil',
            'Nil',
            'https://drive.google.com/file/...',
        ])
        
        return response


class PropertyMapView(LoginRequiredMixin, TemplateView):
    """GIS Map view for visualizing properties on an interactive map."""
    
    template_name = 'property/property_map.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        
        # Role-based property queryset
        user = self.request.user
        org = user.organization if hasattr(user, 'organization') else None
        
        if org and org.is_tma():
            properties = Property.objects.filter(organization=org)
        else:
            properties = Property.objects.all()
        
        # Get filters for sidebar
        context.update({
            'page_title': 'Property Map (GIS)',
            'module_name': 'Property Management',
            'total_properties': properties.count(),
            'property_types': PropertyType.choices,
            'property_statuses': PropertyStatus.choices,
            'districts': District.objects.all(),
        })
        
        return context


class PropertyMapFullscreenView(LoginRequiredMixin, TemplateView):
    """Fullscreen GIS Map view without sidebar/navbar - optimized for analysis."""
    
    template_name = 'property/property_map_fullscreen.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        
        # Role-based property queryset
        user = self.request.user
        org = user.organization if hasattr(user, 'organization') else None
        
        if org and org.is_tma():
            properties = Property.objects.filter(organization=org)
        else:
            properties = Property.objects.all()
        
        # Get filters for floating sidebar
        context.update({
            'page_title': 'Property Map - Fullscreen',
            'total_properties': properties.count(),
            'property_types': PropertyType.choices,
            'property_statuses': PropertyStatus.choices,
            'districts': District.objects.all(),
        })
        
        return context


class PropertyGeoJSONAPIView(LoginRequiredMixin, View):
    """API endpoint to return properties as GeoJSON for map rendering."""
    
    def get(self, request, *args, **kwargs):
        try:
            user = request.user
            
            # Role-based filtering - handle missing organization gracefully
            try:
                org = user.organization
                if org and hasattr(org, 'is_tma') and org.is_tma():
                    properties = Property.objects.filter(organization=org)
                else:
                    properties = Property.objects.all()
            except AttributeError:
                # User has no organization attribute
                properties = Property.objects.all()
            
            # Apply filters from query parameters
            property_type = request.GET.get('type')
            status = request.GET.get('status')
            district_id = request.GET.get('district')
            mauza_id = request.GET.get('mauza')
            search = request.GET.get('search')
            
            if property_type:
                properties = properties.filter(property_type=property_type)
            if status:
                properties = properties.filter(status=status)
            if district_id:
                properties = properties.filter(district_id=district_id)
            if mauza_id:
                properties = properties.filter(mauza_id=mauza_id)
            if search:
                properties = properties.filter(
                    Q(name__icontains=search) |
                    Q(address__icontains=search) |
                    Q(mauza__name__icontains=search)
                )
            
            # Filter only properties with valid GPS coordinates
            properties = properties.exclude(latitude__isnull=True).exclude(longitude__isnull=True)
            
            # Add pagination - limit to 1000 properties for performance
            limit = int(request.GET.get('limit', 1000))
            properties = properties[:limit]
            
            # Optimize query - select only needed fields
            properties = properties.select_related('district', 'mauza', 'organization').only(
                'id', 'name', 'address', 'property_type', 'status', 'area_marlas',
                'annual_rent', 'latitude', 'longitude',
                'district__name', 'mauza__name', 'organization__name'
            )
            
            # Build GeoJSON FeatureCollection
            features = []
            for prop in properties:
                try:
                    # Determine marker color based on status
                    if prop.status == PropertyStatus.RENTED_OUT:
                        color = '#28a745'  # Green
                    elif prop.status == PropertyStatus.VACANT:
                        color = '#dc3545'  # Red
                    elif prop.status == PropertyStatus.UNDER_LITIGATION:
                        color = '#ffc107'  # Yellow
                    elif prop.status == PropertyStatus.SELF_USE:
                        color = '#007bff'  # Blue
                    else:
                        color = '#6c757d'  # Gray
                    
                    # Optimize: Cache display values
                    annual_rent_val = prop.annual_rent or 0
                    
                    feature = {
                        'type': 'Feature',
                        'id': prop.id,
                        'geometry': {
                            'type': 'Point',
                            'coordinates': [float(prop.longitude), float(prop.latitude)]
                        },
                        'properties': {
                            'id': prop.id,
                            'name': prop.name or 'N/A',
                            'status_code': prop.status or '',
                            'status': prop.get_status_display() if prop.status else '',
                            'type': prop.get_property_type_display() if prop.property_type else '',
                            'annual_rent': float(annual_rent_val),
                            'color': color,
                            'district': prop.district.name if prop.district else '',
                            'mauza': prop.mauza.name if prop.mauza else '',
                        }
                    }
                    features.append(feature)
                except Exception as prop_error:
                    logger.error(f"Error processing property {prop.id}: {str(prop_error)}")
                    continue
            
            geojson = {
                'type': 'FeatureCollection',
                'features': features,
                'count': len(features)
            }
            
            return JsonResponse(geojson, safe=False)
            
        except Exception as e:
            logger.error(f"GeoJSON API error: {str(e)}", exc_info=True)
            return JsonResponse({
                'error': 'Failed to load properties',
                'message': str(e),
                'type': type(e).__name__
            }, status=500)


class PropertyDetailAPIView(LoginRequiredMixin, View):
    """API endpoint to return detailed property information."""
    
    def get(self, request, pk, *args, **kwargs):
        try:
            prop = Property.objects.select_related(
                'district', 'mauza', 'village', 'organization'
            ).get(pk=pk)
            
            # Role-based access check
            user = request.user
            org = user.organization if hasattr(user, 'organization') else None
            
            if org and org.is_tma() and prop.organization != org:
                return JsonResponse({'error': 'Access denied'}, status=403)
            
            # Build response
            data = {
                'id': prop.id,
                'name': prop.name,
                'address': prop.address,
                'type': prop.get_property_type_display(),
                'status': prop.get_status_display(),
                'area_marlas': str(prop.area_marlas),
                'area_sqft': str(prop.area_sqft),
                'area_sqm': str(prop.area_sqm),
                'annual_rent': str(prop.annual_rent) if prop.annual_rent else 'N/A',
                'current_tenant': prop.current_tenant.name if prop.current_tenant else 'N/A',
                'district': prop.district.name if prop.district else '',
                'mauza': prop.mauza.name if prop.mauza else '',
                'village': prop.village.name if prop.village else '',
                'organization': prop.organization.name if prop.organization else '',
                'court_case': prop.get_court_case_status_display(),
                'latitude': str(prop.latitude) if prop.latitude else '',
                'longitude': str(prop.longitude) if prop.longitude else '',
                'detail_url': f'/property/properties/{prop.id}/',
                'edit_url': f'/property/properties/{prop.id}/edit/',
            }
            
            return JsonResponse(data)
            
        except Property.DoesNotExist:
            return JsonResponse({'error': 'Property not found'}, status=404)
        except AttributeError as e:
            logger.error(f"PropertyDetailAPIView AttributeError for property {pk}: {str(e)}")
            return JsonResponse({'error': 'Property data incomplete', 'details': str(e)}, status=500)
        except Exception as e:
            logger.error(f"PropertyDetailAPIView error for property {pk}: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Failed to load property details', 'details': str(e)}, status=500)


class PropertyStatsAPIView(LoginRequiredMixin, View):
    """API endpoint to return property statistics for dashboard widgets."""
    
    def get(self, request, *args, **kwargs):
        try:
            user = request.user
            org = user.organization if hasattr(user, 'organization') else None
            
            # Role-based filtering
            if org and org.is_tma():
                properties = Property.objects.filter(organization=org)
            else:
                properties = Property.objects.all()
            
            # Calculate statistics
            stats = {
                'total': properties.count(),
                'rented': properties.filter(status=PropertyStatus.RENTED_OUT).count(),
                'vacant': properties.filter(status=PropertyStatus.VACANT).count(),
                'litigation': properties.exclude(court_case_status=CourtCaseStatus.NO_CASE).count(),
                'self_use': properties.filter(status=PropertyStatus.SELF_USE).count(),
                'by_type': {},
                'by_district': {},
                'by_status': {}
            }
            
            # Group by property type
            for prop_type, label in PropertyType.choices:
                count = properties.filter(property_type=prop_type).count()
                if count > 0:
                    stats['by_type'][label] = count
            
            # Group by status
            for status, label in PropertyStatus.choices:
                count = properties.filter(status=status).count()
                if count > 0:
                    stats['by_status'][label] = count
            
            # Group by district
            district_counts = properties.values('district__name').annotate(count=Count('id')).order_by('-count')
            for item in district_counts:
                if item['district__name']:
                    stats['by_district'][item['district__name']] = item['count']
            
            return JsonResponse(stats)
            
        except Exception as e:
            return JsonResponse({
                'error': 'Failed to calculate statistics',
                'message': str(e)
            }, status=500)
