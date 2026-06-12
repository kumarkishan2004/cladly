"""
Management command to seed Cladly with sample categories and demo data.

Usage:
    python manage.py seed_data
    python manage.py seed_data --admin-email admin@cladly.com --admin-password admin123
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Seed Cladly with sample categories and a superuser admin'

    def add_arguments(self, parser):
        parser.add_argument('--admin-email', default='admin@cladly.com')
        parser.add_argument('--admin-password', default='cladly@admin123')
        parser.add_argument('--admin-name', default='Cladly Admin')

    def handle(self, *args, **options):
        from store.models import User, Category, Coupon

        # ── Admin user
        email = options['admin_email']
        if not User.objects.filter(email=email).exists():
            User.objects.create_superuser(
                email=email,
                password=options['admin_password'],
                full_name=options['admin_name'],
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Superuser created: {email}'))
        else:
            self.stdout.write(f'  Admin {email} already exists.')

        # ── Categories
        categories = [
            ('Earrings',         'earrings',          0),
            ('Ear Studs',        'ear-studs',         1),
            ('Jhumkas',          'jhumkas',           2),
            ('Pendants',         'pendants',          3),
            ('Necklaces',        'necklaces',         4),
            ('Bangles',          'bangles',           5),
            ('Bracelets',        'bracelets',         6),
            ('Rings',            'rings',             7),
            ('Hair Accessories', 'hair-accessories',  8),
            ('Combo Sets',       'combo-sets',        9),
            ('Gift Sets',        'gift-sets',        10),
        ]

        for name, slug, order in categories:
            cat, created = Category.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'is_active': True, 'order': order}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Category: {name}'))

        # ── Sample Coupons
        sample_coupons = [
            {
                'code': 'WELCOME50',
                'description': '₹50 off on first order',
                'discount_type': 'flat',
                'discount_value': 50,
                'minimum_order_value': 299,
                'max_uses': 1000,
                'for_new_users_only': True,
            },
            {
                'code': 'CAMPUS20',
                'description': '20% off for campus students',
                'discount_type': 'percent',
                'discount_value': 20,
                'minimum_order_value': 199,
                'max_uses': 500,
            },
            {
                'code': 'CLADLY10',
                'description': '10% off on all orders',
                'discount_type': 'percent',
                'discount_value': 10,
                'minimum_order_value': 0,
                'max_uses': 9999,
            },
            {
                'code': 'FESTIVE100',
                'description': '₹100 off on festive collection',
                'discount_type': 'flat',
                'discount_value': 100,
                'minimum_order_value': 499,
                'max_uses': 200,
            },
        ]

        now = timezone.now()
        for data in sample_coupons:
            coupon, created = Coupon.objects.get_or_create(
                code=data['code'],
                defaults={
                    **data,
                    'is_active': True,
                    'start_date': now,
                    'expiry_date': now + timedelta(days=365),
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Coupon: {data["code"]}'))

        self.stdout.write(self.style.SUCCESS('\n🎉 Cladly seed data ready!'))
        self.stdout.write(f'\n  Admin login → {email}')
        self.stdout.write(f'  Admin panel → /admin-panel/')
        self.stdout.write(f'  Django admin → /django-admin/\n')
