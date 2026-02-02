"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Forms for System Admin module.
-------------------------------------------------------------------------
"""
from django import forms
from django.core.validators import RegexValidator

from apps.core.models import Organization, Tehsil
from apps.users.models import CustomUser, Role


cnic_validator = RegexValidator(
    regex=r'^\d{5}-\d{7}-\d{1}$',
    message='CNIC must be in format: 12345-1234567-1'
)


class OrganizationForm(forms.ModelForm):
    """Form for creating/editing Organizations (TMAs)."""
    
    class Meta:
        model = Organization
        fields = ['name', 'tehsil', 'org_type', 'ddo_code', 'pla_account_no', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., TMA Abbottabad'
            }),
            'tehsil': forms.Select(attrs={
                'class': 'form-select searchable-select'
            }),
            'org_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'ddo_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., DDO-ABT-001'
            }),
            'pla_account_no': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., PLA-12345'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tehsil'].queryset = Tehsil.objects.filter(
            is_active=True
        ).select_related('district__division').order_by('district__division__name', 'district__name', 'name')


class TenantAdminForm(forms.Form):
    """Form for creating a TMA Admin user."""
    
    cnic = forms.CharField(
        max_length=15,
        validators=[cnic_validator],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '12345-1234567-1'
        }),
        help_text='13-digit CNIC with dashes.'
    )
    
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'admin@example.com'
        })
    )
    
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name'
        })
    )
    
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name'
        })
    )
    
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select',
            'size': '6'
        }),
        help_text='Select roles for this user. TMA Admin role is recommended for system configuration, TMO for transaction approvals.',
        initial=None  # Will be set in __init__
    )
    
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '••••••••'
        })
    )
    
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '••••••••'
        })
    )
    
    is_active = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    def __init__(self, organization=None, request_user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.request_user = request_user
        
        # Filter roles: only superusers can assign SUPER_ADMIN
        if request_user and not request_user.is_superuser:
            self.fields['roles'].queryset = Role.objects.exclude(code='SUPER_ADMIN')
        
        # Default to TMA_ADMIN role for TMA Admins
        try:
            tma_admin_role = Role.objects.get(code='TMA_ADMIN')
            self.fields['roles'].initial = [tma_admin_role.pk]
        except Role.DoesNotExist:
            # Fallback to TMO if TMA_ADMIN doesn't exist
            try:
                tmo_role = Role.objects.get(code='TMO')
                self.fields['roles'].initial = [tmo_role.pk]
            except Role.DoesNotExist:
                pass
    
    def clean_cnic(self):
        """Validate CNIC is unique."""
        cnic = self.cleaned_data.get('cnic')
        if CustomUser.objects.filter(cnic=cnic).exists():
            raise forms.ValidationError('A user with this CNIC already exists.')
        return cnic
    
    def clean_email(self):
        """Validate email is unique if provided."""
        email = self.cleaned_data.get('email')
        if email and CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email
    
    def clean(self):
        """Validate passwords match and role assignment restrictions."""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Passwords do not match.')
        
        # Validate SUPER_ADMIN assignment
        roles = cleaned_data.get('roles', [])
        if roles and self.request_user and not self.request_user.is_superuser:
            super_admin_role = Role.objects.filter(code='SUPER_ADMIN').first()
            if super_admin_role and super_admin_role in roles:
                raise forms.ValidationError(
                    'Only Super Administrators can assign the Super Admin role.'
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Create the user with the assigned role.

        If `commit` is False, return an unsaved `CustomUser` instance so
        the caller can set additional attributes (e.g., organization)
        before saving.
        """
        data = self.cleaned_data

        user = CustomUser(
            cnic=data['cnic'],
            email=data.get('email', ''),
            first_name=data['first_name'],
            last_name=data.get('last_name', ''),
            organization=self.organization,
            is_active=data.get('is_active', True),
            # Note: is_staff and is_superuser remain False for TMA admins
            # Only Provincial Super Admin should have is_superuser=True
        )
        user.set_password(data['password1'])

        if commit:
            user.save()
            # assign roles if provided
            roles = data.get('roles') or []
            if roles:
                user.roles.set(roles)

        return user


from apps.budgeting.models import Department

class UserForm(forms.ModelForm):
    """Form for creating/editing users within a TMA."""
    
    password1 = forms.CharField(
        label='Password',
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password'
        })
    )
    
    password2 = forms.CharField(
        label='Confirm Password',
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
    )
    
    department = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        help_text='Select the administrative wing (Department) for this user.'
    )
    
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        required=True,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select',
            'size': '6'
        }),
        help_text='Select roles to assign to this user.'
    )
    
    class Meta:
        model = CustomUser
        fields = [
            'cnic', 'email', 'first_name', 'last_name', 'department', 'is_active'
        ]
        widgets = {
            'cnic': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '12345-1234567-1'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, is_edit=False, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_edit = is_edit
        self.request_user = request_user
        
        # Filter roles: only superusers can assign SUPER_ADMIN
        if request_user and not request_user.is_superuser:
            self.fields['roles'].queryset = Role.objects.exclude(code='SUPER_ADMIN')
        
        # Populate department choices
        dept_choices = [('', '---------')] + [
            (d.name, str(d)) for d in Department.objects.filter(is_active=True).order_by('name')
        ]
        self.fields['department'].choices = dept_choices
        
        if not is_edit:
            # Password required for new users
            self.fields['password1'].required = True
            self.fields['password2'].required = True
        else:
            # CNIC readonly for edit
            self.fields['cnic'].widget.attrs['readonly'] = True
            
        # Set initial roles if instance exists
        if self.instance.pk:
            self.fields['roles'].initial = self.instance.roles.all()
    
    def clean_cnic(self):
        """Validate CNIC is unique."""
        cnic = self.cleaned_data.get('cnic')
        qs = CustomUser.objects.filter(cnic=cnic)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A user with this CNIC already exists.')
        return cnic
    
    def clean(self):
        """Validate passwords match and role assignment restrictions."""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError('Passwords do not match.')
        
        # Validate SUPER_ADMIN assignment
        roles = cleaned_data.get('roles', [])
        if roles and self.request_user and not self.request_user.is_superuser:
            super_admin_role = Role.objects.filter(code='SUPER_ADMIN').first()
            if super_admin_role and super_admin_role in roles:
                raise forms.ValidationError(
                    'Only Super Administrators can assign the Super Admin role.'
                )
        
        return cleaned_data


class AssignRoleForm(forms.Form):
    """Form for assigning roles to users."""
    
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select',
            'size': '8'
        }),
        help_text='Select roles to assign to this user.'
    )
    
    def __init__(self, *args, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_user = request_user
        
        # Filter roles: only superusers can assign SUPER_ADMIN
        if request_user and not request_user.is_superuser:
            self.fields['roles'].queryset = Role.objects.exclude(code='SUPER_ADMIN')
    
    def clean_roles(self):
        """Validate SUPER_ADMIN assignment."""
        roles = self.cleaned_data.get('roles', [])
        if roles and self.request_user and not self.request_user.is_superuser:
            super_admin_role = Role.objects.filter(code='SUPER_ADMIN').first()
            if super_admin_role and super_admin_role in roles:
                raise forms.ValidationError(
                    'Only Super Administrators can assign the Super Admin role.'
                )
        return roles


class RoleForm(forms.ModelForm):
    """Form for editing Roles."""
    
    class Meta:
        model = Role
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Role Name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Role Description'
            }),
        }


from apps.finance.models import GlobalHead

class GlobalHeadForm(forms.ModelForm):
    """Form for creating/editing Global Heads."""
    
    class Meta:
        model = GlobalHead
        fields = ['code', 'name', 'minor', 'account_type', 'system_code']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. A01101'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Basic Pay - Officers'
            }),
            'minor': forms.Select(attrs={
                'class': 'form-select searchable-select'
            }),
            'account_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'system_code': forms.Select(attrs={
                'class': 'form-select'
            }),
        }

