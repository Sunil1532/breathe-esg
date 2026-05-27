import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Organization, OrganizationMembership


class Command(BaseCommand):
    help = 'Seed demo organization and users for evaluation'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true')

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Deleting existing demo data...')
            User.objects.filter(username__in=['analyst', 'admin_user']).delete()
            Organization.objects.filter(slug='acme-manufacturing').delete()

        org, _ = Organization.objects.get_or_create(
            slug='acme-manufacturing',
            defaults={
                'name': 'Acme Manufacturing GmbH',
                'country_code': 'DE',
                'custom_grid_factor_kg_per_kwh': None,
            }
        )

        analyst_password = os.environ.get('DEMO_ANALYST_PASSWORD', 'analyst123')
        admin_password = os.environ.get('DEMO_ADMIN_PASSWORD', 'admin123')

        for username, password, role, email, first, last, is_staff in [
            ('analyst', analyst_password, OrganizationMembership.ROLE_ANALYST,
             'analyst@acme-mfg.example', 'Ana', 'Lyst', False),
            ('admin_user', admin_password, OrganizationMembership.ROLE_ADMIN,
             'admin@acme-mfg.example', 'Adam', 'Min', True),
        ]:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first,
                    'last_name': last,
                    'is_staff': is_staff,
                }
            )
            if created:
                user.set_password(password)
                user.save()

            OrganizationMembership.objects.update_or_create(
                user=user,
                defaults={'organization': org, 'role': role}
            )

            self.stdout.write(f'  User "{username}" ready, org: {org.name}')

        self.stdout.write(self.style.SUCCESS('\nDemo data ready.'))
        self.stdout.write(f'  analyst / {analyst_password}')
        self.stdout.write(f'  admin_user / {admin_password}')