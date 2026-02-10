"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Unit tests for Property Management models
-------------------------------------------------------------------------
"""
from decimal import Decimal
import unittest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.property.models import (
    District, Mauza, Village, Property,
    PropertyType, PropertySubType, PropertyStatus, CourtCaseStatus
)
from apps.core.models import Organization


class DistrictModelTest(TestCase):
    """Test cases for District model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.district = District.objects.create(
            name='Peshawar',
            code='PSH',
            province='Khyber Pakhtunkhwa'
        )
    
    def test_district_creation(self):
        """Test district can be created successfully."""
        self.assertEqual(self.district.name, 'Peshawar')
        self.assertEqual(self.district.code, 'PSH')
        self.assertEqual(str(self.district), 'Peshawar')
    
    def test_district_unique_name(self):
        """Test district name must be unique."""
        with self.assertRaises(Exception):
            District.objects.create(
                name='Peshawar',
                code='PSH2',
                province='Khyber Pakhtunkhwa'
            )


class MauzaModelTest(TestCase):
    """Test cases for Mauza model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.district = District.objects.create(
            name='Peshawar',
            code='PSH'
        )
        self.mauza = Mauza.objects.create(
            name='Abadai Peshawar',
            district=self.district,
            code='ABPSH'
        )
    
    def test_mauza_creation(self):
        """Test mauza can be created successfully."""
        self.assertEqual(self.mauza.name, 'Abadai Peshawar')
        self.assertEqual(self.mauza.district, self.district)
        self.assertIn('Peshawar', str(self.mauza))
    
    def test_mauza_unique_together(self):
        """Test mauza name must be unique within district."""
        with self.assertRaises(Exception):
            Mauza.objects.create(
                name='Abadai Peshawar',
                district=self.district,
                code='ABPSH2'
            )


class VillageModelTest(TestCase):
    """Test cases for Village model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.district = District.objects.create(name='Peshawar', code='PSH')
        self.mauza = Mauza.objects.create(name='Abadai Peshawar', district=self.district)
        self.village = Village.objects.create(
            name='Kissa Khwani',
            mauza=self.mauza,
            code='KK'
        )
    
    def test_village_creation(self):
        """Test village can be created successfully."""
        self.assertEqual(self.village.name, 'Kissa Khwani')
        self.assertEqual(self.village.mauza, self.mauza)
        self.assertIn('Kissa Khwani', str(self.village))


class PropertyModelTest(TestCase):
    """Test cases for Property model."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create organization
        self.org = Organization.objects.create(
            name='TMA Peshawar',
            org_type='TMA'
        )
        
        # Create location hierarchy
        self.district = District.objects.create(name='Peshawar', code='PSH')
        self.mauza = Mauza.objects.create(name='Abadai Peshawar', district=self.district)
        self.village = Village.objects.create(name='Kissa Khwani', mauza=self.mauza)
        
        # Create property
        self.property = Property.objects.create(
            property_code='PSH-COM-001',
            name='Shop No. 1-A',
            property_type=PropertyType.COMMERCIAL,
            property_sub_type=PropertySubType.SHOP,
            status=PropertyStatus.RENTED_OUT,
            organization=self.org,
            address='Chowk Bazazan, Kissa Khwani',
            district=self.district,
            mauza=self.mauza,
            village=self.village,
            latitude=Decimal('34.0082744'),
            longitude=Decimal('71.5731692'),
            area_marlas=Decimal('0.2022'),
            ownership_title='TMA Peshawar',
            annual_rent=Decimal('120000.00')
        )
    
    def test_property_creation(self):
        """Test property can be created successfully."""
        self.assertEqual(self.property.property_code, 'PSH-COM-001')
        self.assertEqual(self.property.name, 'Shop No. 1-A')
        self.assertEqual(self.property.property_type, PropertyType.COMMERCIAL)
        self.assertIn('PSH-COM-001', str(self.property))
    
    def test_area_conversion(self):
        """Test area is auto-converted to sqft and sqm."""
        # 0.2022 Marlas = 45.495 sq.ft = 4.22598 sq.m
        self.assertIsNotNone(self.property.area_sqft)
        self.assertIsNotNone(self.property.area_sqm)
        self.assertAlmostEqual(
            float(self.property.area_sqft),
            float(self.property.area_marlas * Decimal('225.00')),
            places=2
        )
        self.assertAlmostEqual(
            float(self.property.area_sqm),
            float(self.property.area_marlas * Decimal('20.90')),
            places=2
        )
    
    def test_monthly_rent_calculation(self):
        """Test monthly rent is auto-calculated from annual rent."""
        self.assertIsNotNone(self.property.monthly_rent)
        expected_monthly = self.property.annual_rent / Decimal('12.00')
        self.assertEqual(self.property.monthly_rent, expected_monthly)
    
    def test_property_status_methods(self):
        """Test property status checking methods."""
        self.assertTrue(self.property.is_rented())
        self.assertFalse(self.property.is_vacant())
        
        # Change status and test again
        self.property.status = PropertyStatus.VACANT
        self.property.save()
        self.assertFalse(self.property.is_rented())
        self.assertTrue(self.property.is_vacant())
    
    def test_litigation_status(self):
        """Test litigation status checking."""
        self.assertFalse(self.property.has_litigation())
        
        # Set litigation status
        self.property.court_case_status = CourtCaseStatus.PENDING
        self.property.save()
        self.assertTrue(self.property.has_litigation())
    
    def test_marker_color(self):
        """Test GIS marker color based on status."""
        self.property.status = PropertyStatus.RENTED_OUT
        self.assertEqual(self.property.get_marker_color(), 'green')
        
        self.property.status = PropertyStatus.VACANT
        self.assertEqual(self.property.get_marker_color(), 'red')
        
        self.property.status = PropertyStatus.UNDER_LITIGATION
        self.assertEqual(self.property.get_marker_color(), 'orange')
    
    def test_property_code_unique(self):
        """Test property code must be unique."""
        with self.assertRaises(Exception):
            Property.objects.create(
                property_code='PSH-COM-001',  # Duplicate
                name='Shop No. 2',
                property_type=PropertyType.COMMERCIAL,
                property_sub_type=PropertySubType.SHOP,
                status=PropertyStatus.VACANT,
                organization=self.org,
                address='Test Address',
                district=self.district,
                mauza=self.mauza,
                latitude=Decimal('34.0082'),
                longitude=Decimal('71.5731'),
                area_marlas=Decimal('0.5'),
                ownership_title='TMA',
                annual_rent=Decimal('100000.00')
            )
    
    @unittest.skip("URL patterns not yet implemented - Phase 2")
    def test_get_absolute_url(self):
        """Test get_absolute_url returns correct URL."""
        url = self.property.get_absolute_url()
        self.assertIn(str(self.property.pk), url)
        self.assertIn('property', url)
