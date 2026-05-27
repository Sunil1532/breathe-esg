"""
Management command: python manage.py create_demo_data

Creates a demo Organization, an analyst user, and an admin user so the
deployed app can be tested without manual setup.

Usage:
    python manage.py create_demo_data
    python manage.py create_demo_data --reset   # wipes existing demo data first
"""

import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Organization, OrganizationMembership


class Command(BaseCommand):
    help = 'Seed demo organization and users for evaluation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing demo data before creating fresh records',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Deleting existing demo data...')
            User.objects.filter(username__in=['analyst', 'admin_user']).delete()
            Organization.objects.filter(slug='acme-manufacturing').delete()

        # ── Organization ─────────────────────────────────────────────────
        org, org_created = Organization.objects.get_or_create(
            slug='acme-manufacturing',
            defaults={
                'name': 'Acme Manufacturing GmbH',
                'country_code': 'DE',
                # German grid: 0.434 kg CO2e/kWh (DEFRA 2023 approximation)
                'custom_grid_factor_kg_per_kwh': None,
            }
        )
        status_str = 'created' if org_created else 'already exists'
        self.stdout.write(f'  Organization "{org.name}": {status_str}')

        # ── Analyst user ─────────────────────────────────────────────────
        analyst_password = os.environ.get('DEMO_ANALYST_PASSWORD', 'analyst123')
        analyst, a_created = User.objects.get_or_create(
            username='analyst',
            defaults={
                'email': 'analyst@acme-mfg.example',
                'first_name': 'Ana',
                'last_name': 'Lyst',
            }
        )
        if a_created:
            analyst.set_password(analyst_password)
            analyst.save()
        OrganizationMembership.objects.get_or_create(
            user=analyst,
            defaults={'organization': org, 'role': OrganizationMembership.ROLE_ANALYST}
        )
        a_status = 'created' if a_created else 'already exists'
        self.stdout.write(f'  Analyst user "analyst" (pw: {analyst_password}): {a_status}')

        # ── Admin user ───────────────────────────────────────────────────
        admin_password = os.environ.get('DEMO_ADMIN_PASSWORD', 'admin123')
        admin_user, adm_created = User.objects.get_or_create(
            username='admin_user',
            defaults={
                'email': 'admin@acme-mfg.example',
                'first_name': 'Adam',
                'last_name': 'Min',
                'is_staff': True,
            }
        )
        if adm_created:
            admin_user.set_password(admin_password)
            admin_user.save()
        OrganizationMembership.objects.get_or_create(
            user=admin_user,
            defaults={'organization': org, 'role': OrganizationMembership.ROLE_ADMIN}
        )
        adm_status = 'created' if adm_created else 'already exists'
        self.stdout.write(f'  Admin user "admin_user" (pw: {admin_password}): {adm_status}')

        self.stdout.write(self.style.SUCCESS('\nDemo data ready.'))
        self.stdout.write('  Login credentials:')
        self.stdout.write(f'    Analyst:  username=analyst       password={analyst_password}')
        self.stdout.write(f'    Admin:    username=admin_user    password={admin_password}')
