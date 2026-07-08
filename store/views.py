from django.shortcuts import render, redirect, get_object_or_404
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from datetime import timedelta, date
import json
import random
import string
from .payment_utils import create_razorpay_order, verify_razorpay_payment
from .email_utils import send_welcome_email, send_welcome_back_email, send_password_reset_email
from .password_reset_tokens import generate_reset_token, verify_reset_token, delete_reset_token
from .otp_utils import (
    generate_otp, send_otp_email, store_otp, verify_otp,
    delete_otp, increment_otp_attempts, get_otp_attempts, clear_otp_attempts
)
from .models import (
    CODPincode, ProductSize, User, Category, Product, ProductImage, Address, Cart, Wishlist,
    Order, OrderItem, OrderStatusHistory, Coupon, Review, Banner,
    Notification, RecentlyViewed
)
from .forms import (
    CODPincodeForm, ProductSizeFormSet, RegistrationForm, LoginForm, ForgotPasswordForm, ResetPasswordForm,
    ProfileEditForm, AddressForm, ReviewForm, ProductForm, CategoryForm,
    CouponForm, BannerForm
)

#-------------------------------------------
#Referal
#-----------------------------------------



def _generate_referral_coupon(referrer):
    """Create a unique one-time coupon for the referrer as a reward."""
    code = 'REF' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    coupon = Coupon.objects.create(
        code=code,
        description=f'Referral reward for {referrer.full_name}',
        discount_type='flat',
        discount_value=50,
        minimum_order_value=299,
        max_uses=1,
        start_date=timezone.now(),
        expiry_date=timezone.now() + timedelta(days=15),
        is_active=True,
    )
    return coupon


def _process_referral_reward(order):
    """Give the referrer a reward coupon when their referred friend's FIRST order is delivered."""
    if order.referral_reward_given:
        return
    if not order.user or not order.user.referred_by:
        return
    if order.status != 'delivered':
        return

    referrer = order.user.referred_by

    # Only reward on the referred user's FIRST ever delivered order
    previous_delivered_orders = Order.objects.filter(
        user=order.user, status='delivered'
    ).exclude(id=order.id).count()
    if previous_delivered_orders > 0:
        return
    
    coupon = _generate_referral_coupon(referrer)

    # Track credit value too (for profile display)
    referrer.referral_credits += coupon.discount_value
    referrer.save()

    Notification.objects.create(
        user=referrer,
        title='Referral Reward! 🎉',
        message=f'{order.user.full_name} placed their first order using your referral code! '
                 f'You earned a ₹{coupon.discount_value} coupon: {coupon.code}',
        notif_type='offer',
        link='/profile/',
    )

    order.referral_reward_given = True
    order.save(update_fields=['referral_reward_given'])

    # Send reward email
    try:
        from django.core.mail import send_mail
        from django.conf import settings as dj_settings
        send_mail(
            subject='You earned a referral reward! 🎉 — Cladly',
            message=f"""
Hi {referrer.full_name},

Great news! {order.user.full_name} just placed their first order using your referral code.

As a thank you, here's your reward coupon:

    {coupon.code}

Use it on your next order for ₹{coupon.discount_value} off (minimum order ₹{coupon.minimum_order_value}).
Valid for 15 days.

Keep sharing your referral code — earn more rewards with every friend who orders!

The Cladly Team 🖤
""",
            from_email=dj_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[referrer.email],
            fail_silently=True,
        )
    except Exception:
        pass


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def is_admin(user):
    return user.is_authenticated and user.is_staff


def get_cart_items(request):
    if request.user.is_authenticated:
        return Cart.objects.filter(user=request.user).select_related('product')
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key
    return Cart.objects.filter(session_key=session_key).select_related('product')


def calculate_cart_totals(cart_items, coupon=None):
    subtotal = sum(item.subtotal() for item in cart_items)
    delivery = 0 if subtotal >= 299 else 30
    discount = coupon.get_discount_amount(subtotal) if coupon else 0
    grand_total = subtotal + delivery - discount
    return {
        'subtotal': subtotal,
        'delivery_charge': delivery,
        'discount_amount': discount,
        'grand_total': grand_total,
    }


# ─────────────────────────────────────────────
# HOME
# ─────────────────────────────────────────────

def home(request):
    hero_banners = Banner.objects.filter(banner_type='hero', is_active=True).order_by('order')
    sale_banners = Banner.objects.filter(banner_type='sale', is_active=True)
    flash_banners = Banner.objects.filter(banner_type='flash', is_active=True)
    categories = Category.objects.filter(is_active=True).order_by('order')
    girls_categories = Category.objects.filter(is_active=True, gender='girls').order_by('order')
    boys_categories = Category.objects.filter(is_active=True, gender='boys').order_by('order')
    new_arrivals = Product.objects.filter(is_new_arrival=True, is_active=True)[:12]
    best_sellers = Product.objects.filter(is_best_seller=True, is_active=True)[:12]
    featured = Product.objects.filter(is_featured=True, is_active=True)[:8]

    # Recently viewed
    recently_viewed = []
    if request.user.is_authenticated:
        recently_viewed = RecentlyViewed.objects.filter(
            user=request.user
        ).select_related('product')[:8]

    # Wishlist product ids for UI
    wishlist_ids = []
    if request.user.is_authenticated:
        wishlist_ids = list(Wishlist.objects.filter(
            user=request.user
        ).values_list('product_id', flat=True))

    return render(request, 'store/home.html', {
        'hero_banners': hero_banners,
        'sale_banners': sale_banners,
        'flash_banners': flash_banners,
        'categories': categories,
        'girls_categories': girls_categories,
        'boys_categories': boys_categories,
        'new_arrivals': new_arrivals,
        'best_sellers': best_sellers,
        'featured': featured,
        'recently_viewed': recently_viewed,
        'wishlist_ids': wishlist_ids,
    })


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        # Don't save yet — send OTP first
        email = form.cleaned_data['email']
        full_name = form.cleaned_data['full_name']

        # Store form data in cache temporarily
        import json
        cache_key = f'register_data_{email}'
        cache.set(cache_key, {
            'full_name': full_name,
            'email': email,
            'mobile': form.cleaned_data.get('mobile', ''),
            'password': form.cleaned_data['password'],
            'ref_code': request.GET.get('ref') or request.POST.get('ref_code', ''),
        }, timeout=600)

        # Generate and send OTP
        otp = generate_otp()
        store_otp(email, otp, {'purpose': 'register', 'name': full_name})
        send_otp_email(email, full_name, otp, purpose='register')

        messages.success(request, f'OTP sent to {email}. Please verify to complete registration.')
        return redirect(f'/verify-otp/?identifier={email}&purpose=register&email={email}&name={full_name}')

    return render(request, 'store/auth/register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        identifier = form.cleaned_data['identifier']
        password = form.cleaned_data['password']

        # Try email login
        user = authenticate(request, username=identifier, password=password)
        if not user:
            # Try mobile login
            try:
                u = User.objects.get(mobile=identifier)
                user = authenticate(request, username=u.email, password=password)
            except User.DoesNotExist:
                pass

        if user:
            # Skip OTP for staff/admin — log in directly
            if user.is_staff or user.is_superuser:
                login(request, user)
                return redirect('admin_dashboard')
            # Send OTP before logging in (regular users)
            otp = generate_otp()
            store_otp(user.email, otp, {
                'purpose': 'login',
                'user_id': user.id,
                'name': user.full_name,
            })
            send_otp_email(user.email, user.full_name, otp, purpose='login')

            messages.info(request, f'OTP sent to your email. Please verify to login.')
            return redirect(f'/verify-otp/?identifier={user.email}&purpose=login&email={user.email}&name={user.full_name}')
        else:
            messages.error(request, 'Invalid credentials. Please try again.')

    return render(request, 'store/auth/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')


def forgot_password(request):
    form = ForgotPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        try:
            user = User.objects.get(email=email)
            # Generate token and send email
            token = generate_reset_token(user.id)
            reset_link = f"{settings.FRONTEND_URL}/reset-password/{token}/"
            send_password_reset_email(user, reset_link)
            messages.success(request, 'Password reset link sent! Check your email inbox.')
        except User.DoesNotExist:
            # Show same message even if email not found (security best practice)
            messages.success(request, 'If this email exists, a reset link has been sent.')
    return render(request, 'store/auth/forgot_password.html', {'form': form})

def verify_otp_view(request):
    # GET request — just show the form
    if request.method == 'GET':
        identifier = request.GET.get('identifier', '')
        purpose = request.GET.get('purpose', '')
        email = request.GET.get('email', identifier)
        name = request.GET.get('name', '')
        return render(request, 'store/auth/verify_otp.html', {
            'identifier': identifier,
            'purpose': purpose,
            'email': email,
            'name': name,
            'error': None,
        })

    # POST request — verify the OTP
    identifier = request.POST.get('identifier', '').strip()
    purpose = request.POST.get('purpose', '').strip()
    email = request.POST.get('email', identifier).strip()
    name = request.POST.get('name', '').strip()
    entered_otp = request.POST.get('otp', '').strip()

    # Prevent double submission
    if cache.get(f'otp_used_{identifier}'):
        messages.info(request, 'Login successful!')
        return redirect('home')

    # Check too many wrong attempts
    attempts = get_otp_attempts(identifier)
    if attempts >= 5:
        delete_otp(identifier)
        clear_otp_attempts(identifier)
        messages.error(request, 'Too many wrong attempts. Please request a new OTP.')
        return redirect('register' if purpose == 'register' else 'login')

    # Get OTP data from cache directly
    otp_data = cache.get(f'otp_{identifier}')

    # Check if OTP expired
    if not otp_data:
        messages.error(request, 'OTP expired. Please request a new one.')
        return redirect('register' if purpose == 'register' else 'login')

    # Compare OTP
    stored_otp = str(otp_data.get('otp', '')).strip()
    entered_otp_clean = str(entered_otp).strip()

    if stored_otp == entered_otp_clean:
        # ── CORRECT OTP ──

        # Mark as used immediately — blocks any second submission
        cache.set(f'otp_used_{identifier}', True, timeout=60)
        # Delete OTP from cache
        delete_otp(identifier)
        clear_otp_attempts(identifier)

        if purpose == 'register':
            reg_data = cache.get(f'register_data_{identifier}')
            if reg_data:
                # Check if user already created (double submit safety)
                if User.objects.filter(email=reg_data['email']).exists():
                    user = User.objects.get(email=reg_data['email'])
                    login(request, user)
                    return redirect('home')

                user = User(
                    full_name=reg_data['full_name'],
                    email=reg_data['email'],
                    mobile=reg_data.get('mobile', ''),
                )
                user.set_password(reg_data['password'])
                if reg_data.get('ref_code'):
                    try:
                        referrer = User.objects.get(referral_code=reg_data['ref_code'])
                        user.referred_by = referrer
                    except User.DoesNotExist:
                        pass
                user.save()
                cache.delete(f'register_data_{identifier}')
                login(request, user)
                _merge_guest_cart(request, user)
                send_welcome_email(user)
                messages.success(request, f'Welcome to Cladly, {user.full_name}! 🎉')
                return redirect('home')
            else:
                messages.error(request, 'Session expired. Please register again.')
                return redirect('register')

        elif purpose == 'login':
            user_id = otp_data.get('user_id')
            if not user_id:
                messages.error(request, 'Something went wrong. Please login again.')
                return redirect('login')
            try:
                user = User.objects.get(id=user_id)
                login(request, user)
                _merge_guest_cart(request, user)
                send_welcome_back_email(user)
                messages.success(request, f'Welcome back, {user.full_name}! 👋')
                return redirect('home')
            except User.DoesNotExist:
                messages.error(request, 'Something went wrong. Please login again.')
                return redirect('login')

    else:
        # ── WRONG OTP ──
        attempts = increment_otp_attempts(identifier)
        remaining = 5 - attempts
        if remaining > 0:
            error = f'Wrong OTP. {remaining} attempt{"s" if remaining > 1 else ""} remaining.'
        else:
            delete_otp(identifier)
            clear_otp_attempts(identifier)
            messages.error(request, 'Too many wrong attempts. Please request a new OTP.')
            return redirect('register' if purpose == 'register' else 'login')

        return render(request, 'store/auth/verify_otp.html', {
            'identifier': identifier,
            'purpose': purpose,
            'email': email,
            'name': name,
            'error': error,
        })
    
    
def resend_otp(request):
    if request.method == 'POST':
        identifier = request.POST.get('identifier')
        purpose = request.POST.get('purpose')
        email = request.POST.get('email', identifier)
        name = request.POST.get('name', '')

        clear_otp_attempts(identifier)
        otp = generate_otp()
        store_otp(identifier, otp, {
            'purpose': purpose,
            'name': name,
        })
        send_otp_email(email, name, otp, purpose=purpose)
        messages.success(request, 'New OTP sent to your email!')

    return redirect(f'/verify-otp/?identifier={identifier}&purpose={purpose}&email={email}&name={name}')




def reset_password(request, token):
    # Verify token is valid
    user_id = verify_reset_token(token)
    if not user_id:
        messages.error(request, 'This reset link is invalid or has expired. Please request a new one.')
        return redirect('forgot_password')

    form = ResetPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            user = User.objects.get(id=user_id)
            user.set_password(form.cleaned_data['password'])
            user.save()
            # Delete token so it cannot be reused
            delete_reset_token(token)
            messages.success(request, 'Password reset successfully! You can now login.')
            return redirect('login')
        except User.DoesNotExist:
            messages.error(request, 'Something went wrong. Please try again.')
            return redirect('forgot_password')

    return render(request, 'store/auth/reset_password.html', {'form': form, 'token': token})


def _merge_guest_cart(request, user):
    session_key = request.session.session_key
    if session_key:
        guest_items = Cart.objects.filter(session_key=session_key)
        for item in guest_items:
            existing = Cart.objects.filter(user=user, product=item.product).first()
            if existing:
                existing.quantity += item.quantity
                existing.save()
                item.delete()
            else:
                item.user = user
                item.session_key = None
                item.save()


# ─────────────────────────────────────────────
# PRODUCTS
# ─────────────────────────────────────────────

def product_list(request):
    products = Product.objects.filter(is_active=True).prefetch_related('images')
    return _apply_product_filters(request, products, 'store/products/list.html', {})


def category_products(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    products = Product.objects.filter(category=category, is_active=True).prefetch_related('images')
    return _apply_product_filters(request, products, 'store/products/category.html', {'current_category': category})


def _apply_product_filters(request, queryset, template, extra_ctx):
    # Filters
    sort = request.GET.get('sort', '')
    color = request.GET.get('color', '')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    if request.GET.get('new_arrivals'):
        queryset = queryset.filter(is_new_arrival=True)
    if request.GET.get('best_sellers'):
        queryset = queryset.filter(is_best_seller=True)
    if request.GET.get('on_sale'):
        queryset = queryset.filter(selling_price__lt=models_original_price_ref())
    if color:
        queryset = queryset.filter(color__icontains=color)
    if min_price:
        queryset = queryset.filter(selling_price__gte=min_price)
    if max_price:
        queryset = queryset.filter(selling_price__lte=max_price)

    if sort == 'price_low':
        queryset = queryset.order_by('selling_price')
    elif sort == 'price_high':
        queryset = queryset.order_by('-selling_price')
    elif sort == 'newest':
        queryset = queryset.order_by('-created_at')
    elif sort == 'discount':
        queryset = queryset.extra(
            select={'discount': '(original_price - selling_price) * 100 / original_price'}
        ).order_by('-discount')

    wishlist_ids = []
    if request.user.is_authenticated:
        wishlist_ids = list(Wishlist.objects.filter(
            user=request.user
        ).values_list('product_id', flat=True))

    paginator = Paginator(queryset, 20)
    page = paginator.get_page(request.GET.get('page', 1))

    ctx = {
        'products': page,
        'categories': Category.objects.filter(is_active=True),
        'wishlist_ids': wishlist_ids,
        'current_sort': sort,
        'current_color': color,
    }
    ctx.update(extra_ctx)
    return render(request, template, ctx)


def models_original_price_ref():
    from django.db.models import F
    return F('original_price')


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)

    # Track recently viewed
    if request.user.is_authenticated:
        RecentlyViewed.objects.update_or_create(
            user=request.user, product=product,
            defaults={'viewed_at': timezone.now()}
        )
    else:
        if not request.session.session_key:
            request.session.create()
        RecentlyViewed.objects.update_or_create(
            session_key=request.session.session_key, product=product,
            defaults={'viewed_at': timezone.now()}
        )

    related_products = Product.objects.filter(
        category=product.category, is_active=True
    ).exclude(id=product.id)[:8]

    reviews = product.reviews.filter(is_approved=True).select_related('user')
    review_form = ReviewForm()

    # Check if user already reviewed
    user_review = None
    can_review = False
    if request.user.is_authenticated:
        user_review = reviews.filter(user=request.user).first()
        can_review = OrderItem.objects.filter(
            order__user=request.user,
            order__status='delivered',
            product=product
        ).exists()

    wishlist_ids = []
    if request.user.is_authenticated:
        wishlist_ids = list(Wishlist.objects.filter(
            user=request.user
        ).values_list('product_id', flat=True))

    return render(request, 'store/products/detail.html', {
        'product': product,
        'related_products': related_products,
        'reviews': reviews,
        'review_form': review_form,
        'user_review': user_review,
        'can_review': can_review,
        'wishlist_ids': wishlist_ids,
    })


def search(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.none()
    if query:
        products = Product.objects.filter(
            is_active=True
        ).filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query) |
            Q(color__icontains=query) |
            Q(tags__icontains=query)
        ).prefetch_related('images')

    wishlist_ids = []
    if request.user.is_authenticated:
        wishlist_ids = list(Wishlist.objects.filter(
            user=request.user
        ).values_list('product_id', flat=True))

    paginator = Paginator(products, 20)
    page = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'store/products/search.html', {
        'products': page,
        'query': query,
        'wishlist_ids': wishlist_ids,
    })


def search_suggestions(request):
    query = request.GET.get('q', '').strip()
    suggestions = []
    if len(query) >= 2:
        products = Product.objects.filter(
            is_active=True
        ).filter(
            Q(name__icontains=query) |
            Q(category__name__icontains=query) |
            Q(color__icontains=query)
        ).values('id', 'name', 'selling_price', 'slug')[:8]

        for p in products:
            product = Product.objects.get(id=p['id'])
            img = product.primary_image()
            suggestions.append({
                'id': p['id'],
                'name': p['name'],
                'price': str(p['selling_price']),
                'slug': p['slug'],
                'image': img.image.url if img and img.image else '',
            })
    return JsonResponse({'suggestions': suggestions})


# ─────────────────────────────────────────────
# CART
# ─────────────────────────────────────────────

def cart_view(request):
    cart_items = get_cart_items(request)
    coupon = _get_session_coupon(request)
    totals = calculate_cart_totals(cart_items, coupon)
    return render(request, 'store/cart/cart.html', {
        'cart_items': cart_items,
        'coupon': coupon,
        **totals,
    })


def add_to_cart(request, product_id):

    product = get_object_or_404(Product, id=product_id)
    quantity = int(request.POST.get('quantity', 1))
    size_id = request.POST.get('size_id') or None
    size_obj = ProductSize.objects.filter(id=size_id).first() if size_id else None

    if request.user.is_authenticated:
        cart_item, created = Cart.objects.get_or_create(
            user=request.user, product=product, size=size_obj,
            defaults={'quantity': quantity}
        )
    else:
        if not request.session.session_key:
            request.session.create()
        cart_item, created = Cart.objects.get_or_create(
            session_key=request.session.session_key, product=product, size=size_obj,
            defaults={'quantity': quantity}
        )

    if not created:
        cart_item.quantity += quantity
        cart_item.save()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})

    return redirect('cart')



def update_cart(request, item_id):
    item = get_object_or_404(Cart, id=item_id)
    qty = int(request.POST.get('quantity', 1))
    if qty > 0:
        item.quantity = qty
        item.save()
    else:
        item.delete()
    return redirect('cart')


def remove_from_cart(request, item_id):
    item = get_object_or_404(Cart, id=item_id)
    item.delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    messages.success(request, 'Item removed from cart.')
    return redirect('cart')


def apply_coupon(request):
    code = request.POST.get('coupon_code', '').strip().upper()
    try:
        coupon = Coupon.objects.get(code=code)
        if not coupon.is_valid():
            messages.error(request, 'This coupon has expired or is inactive.')
        else:
            cart_items = get_cart_items(request)
            totals = calculate_cart_totals(cart_items)
            if totals['subtotal'] < float(coupon.minimum_order_value):
                messages.error(request, f'Minimum order of ₹{coupon.minimum_order_value} required.')
            else:
                request.session['coupon_id'] = coupon.id
                messages.success(request, f'Coupon "{code}" applied successfully!')
    except Coupon.DoesNotExist:
        messages.error(request, 'Invalid coupon code.')
    return redirect('cart')


def remove_coupon(request):
    request.session.pop('coupon_id', None)
    messages.success(request, 'Coupon removed.')
    return redirect('cart')


def _get_session_coupon(request):
    coupon_id = request.session.get('coupon_id')
    if coupon_id:
        try:
            return Coupon.objects.get(id=coupon_id)
        except Coupon.DoesNotExist:
            request.session.pop('coupon_id', None)
    return None


# ─────────────────────────────────────────────
# WISHLIST
# ─────────────────────────────────────────────

@login_required
def wishlist_view(request):
    items = Wishlist.objects.filter(user=request.user).select_related('product').prefetch_related('product__images')
    return render(request, 'store/user/wishlist.html', {'wishlist_items': items})


@login_required
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if not created:
        item.delete()
        added = False
    else:
        added = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'added': added, 'wishlist_count': Wishlist.objects.filter(user=request.user).count()})
    return redirect(request.META.get('HTTP_REFERER', 'wishlist'))


@login_required
def move_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    Wishlist.objects.filter(user=request.user, product=product).delete()
    item, created = Cart.objects.get_or_create(user=request.user, product=product)
    if not created:
        item.quantity += 1
        item.save()
    messages.success(request, 'Moved to cart!')
    return redirect('wishlist')


# ─────────────────────────────────────────────
# CHECKOUT & ORDERS
# ─────────────────────────────────────────────

@login_required
def checkout(request):

    # If there's a pending Razorpay payment in session, clear it
    # (customer went back to checkout after abandoning payment page)

    if 'pending_order' in request.session:
        request.session.pop('pending_order', None)
        request.session.pop('razorpay_order_id', None)
     

    cart_items = get_cart_items(request)
    if not cart_items.exists():
        messages.warning(request, 'Your cart is empty.')
        return redirect('cart')

    coupon = _get_session_coupon(request)
    totals = calculate_cart_totals(cart_items, coupon)
    addresses = Address.objects.filter(user=request.user)
    address_form = AddressForm()

    cod_pincodes = list(CODPincode.objects.filter(is_active=True).values_list('pincode', flat=True))

    return render(request, 'store/orders/checkout.html', {
        'cart_items': cart_items,
        'addresses': addresses,
        'address_form': address_form,
        'coupon': coupon,
        'cod_pincodes_json': json.dumps(cod_pincodes),
        **totals,
    })
 
@login_required
@require_POST

def place_order(request):
    cart_items = get_cart_items(request)
    if not cart_items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('cart')

    address_id = request.POST.get('address_id')
    payment_method = request.POST.get('payment_method', 'cod')

    # Handle new address
    if address_id == 'new':
        form = AddressForm(request.POST)
        if form.is_valid():
            addr = form.save(commit=False)
            addr.user = request.user
            addr.save()
            address_id = addr.id
        else:
            messages.error(request, 'Please fill in the delivery address correctly.')
            return redirect('checkout')

    address = get_object_or_404(Address, id=address_id, user=request.user)

    # ── COD pincode check — block before creating the order ──
    if payment_method == 'cod':
        if not CODPincode.objects.filter(pincode=address.pincode, is_active=True).exists():
            messages.error(request, f'Cash on Delivery is not available for pincode {address.pincode}. Please pay online instead.')
            return redirect('checkout')

    coupon = _get_session_coupon(request)
    totals = calculate_cart_totals(cart_items, coupon)

   # ── COD — create order immediately ──
    if payment_method == 'cod':
        order = _create_order(request, address, payment_method, coupon, totals, cart_items)
        cart_items.delete()
        Notification.objects.create(
            user=request.user,
            title='Order Placed!',
            message=f'Your order {order.order_id} has been placed successfully.',
            notif_type='order',
            link=f'/orders/{order.order_id}/',
        )
        _process_referral_reward(order)
        return redirect('order_success', order_id=order.order_id)

    # ── Online payment — save intent to session, open Razorpay ──
    else:
        # Store everything needed to create the order after payment
        request.session['pending_order'] = {
            'address_id': str(address.id),
            'payment_method': payment_method,
            'coupon_id': coupon.id if coupon else None,
        }

        # Create Razorpay payment order (just a payment intent — not your Order model)
        try:
            razorpay_order = create_razorpay_order(totals['grand_total'], 'PENDING')
        except Exception as e:
            messages.error(request, 'Payment gateway error. Please try again.')
            return redirect('checkout')

        request.session['razorpay_order_id'] = razorpay_order['id']

        return render(request, 'store/orders/payment.html', {
            'razorpay_order_id': razorpay_order['id'],
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'amount': int(float(totals['grand_total']) * 100),
            'grand_total': totals['grand_total'],
            'user_name': request.user.full_name,
            'user_email': request.user.email,
            'user_mobile': request.user.mobile or '',
        })


def _create_order(request, address, payment_method, coupon, totals, cart_items):
    """Creates Order + OrderItems + reduces stock. Used by both COD and online payment."""
    order = Order.objects.create(
        user=request.user,
        address=address,
        delivery_name=address.name,
        delivery_mobile=address.mobile,
        delivery_address=address.address_line,
        delivery_college=address.college_name,
        delivery_city=address.city,
        delivery_pincode=address.pincode,
        payment_method=payment_method,
        coupon=coupon,
        coupon_code=coupon.code if coupon else '',
        expected_delivery=date.today() + timedelta(days=1),
        **totals,
    )

    for item in cart_items:
        img = item.product.primary_image()
        OrderItem.objects.create(
            order=order,
            product=item.product,
            product_name=item.product.name,
            product_image=img.image.url if img and img.image else '',
            size_label=item.size.size_label if item.size else 'Free Size',
            quantity=item.quantity,
            price=item.product.selling_price,
            original_price=item.product.original_price,
        )

        if item.size:
            item.size.stock_quantity = max(0, item.size.stock_quantity - item.quantity)
            item.size.save()
            item.product.stock_quantity = sum(s.stock_quantity for s in item.product.sizes.all())
        else:
            item.product.stock_quantity = max(0, item.product.stock_quantity - item.quantity)

        item.product.update_stock_status()

    if coupon:
        coupon.used_count += 1
        coupon.save()
        request.session.pop('coupon_id', None)

    OrderStatusHistory.objects.create(
        order=order,
        status='placed',
        note='Order placed successfully.'
    )

    return order


@require_POST
def verify_payment(request):
    razorpay_order_id = request.POST.get('razorpay_order_id')
    razorpay_payment_id = request.POST.get('razorpay_payment_id')
    razorpay_signature = request.POST.get('razorpay_signature')

    # Verify Razorpay signature first
    is_valid = verify_razorpay_payment(
        razorpay_order_id,
        razorpay_payment_id,
        razorpay_signature
    )

    if not is_valid:
        messages.error(request, 'Payment verification failed. Please contact support.')
        request.session.pop('pending_order', None)
        request.session.pop('razorpay_order_id', None)
        return redirect('checkout')

    # Payment is genuine — now create the actual order
    pending = request.session.get('pending_order')
    if not pending:
        messages.error(request, 'Session expired. Please try again.')
        return redirect('checkout')

    try:
        address = get_object_or_404(Address, id=pending['address_id'], user=request.user)
        payment_method = pending.get('payment_method', 'online')
        coupon_id = pending.get('coupon_id')
        coupon = Coupon.objects.filter(id=coupon_id).first() if coupon_id else None

        cart_items = get_cart_items(request)
        if not cart_items.exists():
            messages.error(request, 'Your cart appears to be empty. Please contact support with your payment ID.')
            return redirect('home')

        totals = calculate_cart_totals(cart_items, coupon)

        # Create the order now that payment is confirmed
        order = _create_order(request, address, payment_method, coupon, totals, cart_items)

        # Save Razorpay payment details on the order
        order.razorpay_order_id = razorpay_order_id
        order.razorpay_payment_id = razorpay_payment_id
        order.razorpay_signature = razorpay_signature
        order.status = 'confirmed'
        order.save()

        # Clear cart and session
        cart_items.delete()
        request.session.pop('pending_order', None)
        request.session.pop('razorpay_order_id', None)

        OrderStatusHistory.objects.create(
            order=order,
            status='confirmed',
            note=f'Payment received online. Payment ID: {razorpay_payment_id}'
        )

        Notification.objects.create(
            user=request.user,
            title='Payment Successful! 🎉',
            message=f'Payment for order {order.order_id} received. Your order is confirmed.',
            notif_type='order',
            link=f'/orders/{order.order_id}/',
        )

        _process_referral_reward(order)

        return redirect('order_success', order_id=order.order_id)

    except Exception as e:
        # Payment was real but order creation failed — critical, log this
        print(f"CRITICAL: Payment {razorpay_payment_id} succeeded but order creation failed: {e}")
        messages.error(request, f'Payment received (ID: {razorpay_payment_id}) but order creation failed. Please contact support immediately with this payment ID.')
        return redirect('home')

@login_required
def payment_failed(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    return render(request, 'store/orders/payment_failed.html', {'order': order})



@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    return render(request, 'store/orders/order_success.html', {'order': order})


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items')
    active = orders.exclude(status__in=['delivered', 'cancelled'])
    past = orders.filter(status__in=['delivered', 'cancelled'])
    return render(request, 'store/user/orders.html', {'active_orders': active, 'past_orders': past})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    return render(request, 'store/orders/order_detail.html', {'order': order})


@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)

    if order.status not in ['placed', 'confirmed','packed','out_for_delivery']:
        messages.error(request, f'Order cannot be cancelled at "{order.get_status_display()}" stage.')
        return redirect('order_detail', order_id=order_id)

    if request.method == 'POST':
        reason = request.POST.get('cancel_reason', '').strip()

        order.status = 'cancelled'
        order.cancel_reason = reason
        order.cancelled_at = timezone.now()
        order.save()

        # Restore stock
        for item in order.items.all():
            if item.product:
                item.product.stock_quantity += item.quantity
                item.product.update_stock_status()

        # Status history
        OrderStatusHistory.objects.create(
            order=order,
            status='cancelled',
            note=f'Cancelled by customer. Reason: {reason if reason else "Not provided"}'
        )

        # Notification
        Notification.objects.create(
            user=request.user,
            title='Order Cancelled',
            message=f'Your order {order.order_id} has been cancelled successfully.',
            notif_type='order',
            link=f'/orders/{order.order_id}/',
        )

        # Send cancellation email
        from .email_utils import send_order_cancelled_email
        send_order_cancelled_email(request.user, order)

        messages.success(request, f'Order {order.order_id} cancelled successfully.')
        return redirect('my_orders')

    # GET — show cancel confirmation page
    return render(request, 'store/orders/cancel_order.html', {'order': order})


@login_required
def thank_you_card(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    return render(request, 'store/orders/thank_you_card.html', {'order': order})


# ─────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────

@login_required
def profile(request):
    orders_count = Order.objects.filter(user=request.user).count()
    wishlist_count = Wishlist.objects.filter(user=request.user).count()

    referral_count = User.objects.filter(referred_by=request.user).count()
    successful_referrals = Order.objects.filter(
        user__referred_by=request.user, referral_reward_given=True
    ).count()
    my_referral_coupons = Coupon.objects.filter(
        description__icontains=request.user.full_name,
        code__startswith='REF'
    ).order_by('-created_at')

    return render(request, 'store/user/profile.html', {
        'orders_count': orders_count,
        'wishlist_count': wishlist_count,
        'referral_count': referral_count,
        'successful_referrals': successful_referrals,
        'my_referral_coupons': my_referral_coupons,
    })

@login_required
def edit_profile(request):
    form = ProfileEditForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')
    return render(request, 'store/user/edit_profile.html', {'form': form})


@login_required
def change_password(request):
    if request.method == 'POST':
        current = request.POST.get('current_password')
        new = request.POST.get('new_password')
        confirm = request.POST.get('confirm_password')
        if not request.user.check_password(current):
            messages.error(request, 'Current password is incorrect.')
        elif new != confirm:
            messages.error(request, 'New passwords do not match.')
        elif len(new) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
        else:
            request.user.set_password(new)
            request.user.save()
            messages.success(request, 'Password changed. Please log in again.')
            return redirect('login')
    return render(request, 'store/user/change_password.html')


# ─────────────────────────────────────────────
# ADDRESSES
# ─────────────────────────────────────────────

@login_required
def address_list(request):
    addresses = Address.objects.filter(user=request.user)
    return render(request, 'store/user/addresses.html', {'addresses': addresses})


@login_required
def add_address(request):
    form = AddressForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        addr = form.save(commit=False)
        addr.user = request.user
        addr.save()
        messages.success(request, 'Address added.')
        return redirect(request.GET.get('next', 'address_list'))
    return render(request, 'store/user/address_form.html', {'form': form, 'action': 'Add'})


@login_required
def edit_address(request, pk):
    addr = get_object_or_404(Address, pk=pk, user=request.user)
    form = AddressForm(request.POST or None, instance=addr)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Address updated.')
        return redirect('address_list')
    return render(request, 'store/user/address_form.html', {'form': form, 'action': 'Edit'})


@login_required
def delete_address(request, pk):
    addr = get_object_or_404(Address, pk=pk, user=request.user)
    addr.delete()
    messages.success(request, 'Address deleted.')
    return redirect('address_list')


@login_required
def set_default_address(request, pk):
    addr = get_object_or_404(Address, pk=pk, user=request.user)
    Address.objects.filter(user=request.user).update(is_default=False)
    addr.is_default = True
    addr.save()
    return redirect('address_list')


# ─────────────────────────────────────────────
# REVIEWS
# ─────────────────────────────────────────────

@login_required
@require_POST
def submit_review(request, slug):
    product = get_object_or_404(Product, slug=slug)
    form = ReviewForm(request.POST, request.FILES)
    if form.is_valid():
        review, created = Review.objects.update_or_create(
            product=product, user=request.user,
            defaults={
                'rating': form.cleaned_data['rating'],
                'title': form.cleaned_data['title'],
                'content': form.cleaned_data['content'],
                'image': form.cleaned_data.get('image'),
            }
        )
        messages.success(request, 'Review submitted. Thank you!')
    else:
        messages.error(request, 'Please fill in the review form correctly.')
    return redirect('product_detail', slug=slug)


# ─────────────────────────────────────────────
# NOTIFICATIONS
# ─────────────────────────────────────────────

@login_required
def notifications(request):
    notifs = Notification.objects.filter(user=request.user)
    return render(request, 'store/user/notifications.html', {'notifications': notifs})


@login_required
def mark_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})


# ─────────────────────────────────────────────
# ADMIN DASHBOARD
# ─────────────────────────────────────────────

@user_passes_test(is_admin, login_url='/login/')
def admin_dashboard(request):
    today = timezone.now().date()
    week_start = today - timedelta(days=7)
    month_start = today.replace(day=1)

    daily_orders = Order.objects.filter(placed_at__date=today)
    weekly_orders = Order.objects.filter(placed_at__date__gte=week_start)
    monthly_orders = Order.objects.filter(placed_at__date__gte=month_start)

    daily_revenue = daily_orders.aggregate(total=Sum('grand_total'))['total'] or 0
    weekly_revenue = weekly_orders.aggregate(total=Sum('grand_total'))['total'] or 0
    monthly_revenue = monthly_orders.aggregate(total=Sum('grand_total'))['total'] or 0
    total_revenue = Order.objects.aggregate(total=Sum('grand_total'))['total'] or 0

    best_sellers = OrderItem.objects.values(
        'product__name', 'product__id'
    ).annotate(total_sold=Sum('quantity')).order_by('-total_sold')[:10]

    low_stock = Product.objects.filter(stock_status='low_stock')
    out_of_stock = Product.objects.filter(stock_status='out_of_stock')
    pending_orders = Order.objects.filter(status='placed').count()
    total_customers = User.objects.filter(is_staff=False).count()
    total_products = Product.objects.filter(is_active=True).count()

    recent_orders = Order.objects.order_by('-placed_at')[:10]

    return render(request, 'store/admin/dashboard.html', {
        'daily_revenue': daily_revenue,
        'weekly_revenue': weekly_revenue,
        'monthly_revenue': monthly_revenue,
        'total_revenue': total_revenue,
        'daily_orders': daily_orders.count(),
        'weekly_orders': weekly_orders.count(),
        'monthly_orders': monthly_orders.count(),
        'total_orders': Order.objects.count(),
        'best_sellers': best_sellers,
        'low_stock': low_stock,
        'out_of_stock': out_of_stock,
        'pending_orders': pending_orders,
        'total_customers': total_customers,
        'total_products': total_products,
        'recent_orders': recent_orders,
    })


@user_passes_test(is_admin, login_url='/login/')
def admin_products(request):
    products = Product.objects.all().select_related('category').prefetch_related('images')
    q = request.GET.get('q')
    if q:
        products = products.filter(Q(name__icontains=q) | Q(category__name__icontains=q))
    paginator = Paginator(products, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'store/admin/products.html', {'products': page})


@user_passes_test(is_admin, login_url='/login/')
def admin_add_product(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    size_formset = ProductSizeFormSet(request.POST or None, prefix='sizes')

    if request.method == 'POST' and form.is_valid():
        product = form.save()
        images = request.FILES.getlist('images')
        for i, img in enumerate(images):
            ProductImage.objects.create(product=product, image=img, is_primary=(i == 0), order=i)

        size_formset.instance = product
        if size_formset.is_valid():
            size_formset.save()

        # Keep main stock_quantity in sync as the sum of all sizes, only if sizes were added
        if product.sizes.exists():
            product.stock_quantity = sum(s.stock_quantity for s in product.sizes.all())
            product.update_stock_status()

        messages.success(request, 'Product created.')
        return redirect('admin_products')

    return render(request, 'store/admin/product_form.html', {
        'form': form, 'size_formset': size_formset, 'action': 'Add'
    })

@user_passes_test(is_admin, login_url='/login/')
def admin_edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    size_formset = ProductSizeFormSet(request.POST or None, instance=product, prefix='sizes')

    if request.method == 'POST' and form.is_valid():
        form.save()
        images = request.FILES.getlist('images')
        for i, img in enumerate(images):
            ProductImage.objects.create(product=product, image=img, order=product.images.count() + i)

        if size_formset.is_valid():
            size_formset.save()

        if product.sizes.exists():
            product.stock_quantity = sum(s.stock_quantity for s in product.sizes.all())
            product.update_stock_status()

        messages.success(request, 'Product updated.')
        return redirect('admin_products')

    return render(request, 'store/admin/product_form.html', {
        'form': form, 'size_formset': size_formset, 'action': 'Edit', 'product': product
    })

@user_passes_test(is_admin, login_url='/login/')
def admin_delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted.')
        return redirect('admin_products')
    return render(request, 'store/admin/confirm_delete.html', {'object': product, 'type': 'Product'})


@user_passes_test(is_admin, login_url='/login/')
def admin_categories(request):
    cats = Category.objects.annotate(prod_count=Count('products'))
    return render(request, 'store/admin/categories.html', {'categories': cats})


@user_passes_test(is_admin, login_url='/login/')
def admin_add_category(request):
    form = CategoryForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created successfully!')
            return redirect('admin_categories')
        else:
            # Show what went wrong
            print("Form errors:", form.errors)
    return render(request, 'store/admin/category_form.html', {'form': form, 'action': 'Add'})


@user_passes_test(is_admin, login_url='/login/')
def admin_edit_category(request, pk):
    cat = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, request.FILES or None, instance=cat)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Category updated.')
        return redirect('admin_categories')
    return render(request, 'store/admin/category_form.html', {'form': form, 'action': 'Edit'})


@user_passes_test(is_admin, login_url='/login/')
def admin_delete_category(request, pk):
    cat = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        cat.delete()
        messages.success(request, 'Category deleted.')
        return redirect('admin_categories')
    return render(request, 'store/admin/confirm_delete.html', {'object': cat, 'type': 'Category'})


@user_passes_test(is_admin, login_url='/login/')
def admin_orders(request):
    orders = Order.objects.all().select_related('user').prefetch_related('items')
    
    # Search
    search_query = request.GET.get('q', '').strip()
    if search_query:
        orders = orders.filter(
            Q(order_id__icontains=search_query) |
            Q(delivery_name__icontains=search_query) |
            Q(delivery_mobile__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )

    # Status filter

    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    paginator = Paginator(orders, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'store/admin/orders.html', {
        'orders': page,
        'search_query': search_query,
        'status_choices': Order.STATUS_CHOICES,
        'current_status': status_filter,
    })


@user_passes_test(is_admin, login_url='/login/')
def admin_order_detail(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    return render(request, 'store/admin/order_detail.html', {
        'order': order,
        'status_choices': Order.STATUS_CHOICES,
    })

@user_passes_test(is_admin, login_url='/login/')
def admin_shipping_label(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    return render(request, 'store/admin/shipping_label.html', {'order': order})


@user_passes_test(is_admin, login_url='/login/')
def admin_invoice(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    return render(request, 'store/admin/invoice.html', {'order': order})



@user_passes_test(is_admin, login_url='/login/')
@require_POST
def admin_update_order_status(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    new_status = request.POST.get('status')
    note = request.POST.get('note', '')
    if new_status in dict(Order.STATUS_CHOICES):
        order.status = new_status
        order.save()
        OrderStatusHistory.objects.create(order=order, status=new_status, note=note)
        if order.user:
            status_display = dict(Order.STATUS_CHOICES).get(new_status, new_status)
            Notification.objects.create(
                user=order.user,
                title=f'Order {status_display}',
                message=f'Your order {order.order_id} is now {status_display}.',
                notif_type='order',
                link=f'/orders/{order.order_id}/',
            )

        # Referral reward — only trigger once the order is actually delivered
        if new_status == 'delivered':
            _process_referral_reward(order)

        messages.success(request, f'Order status updated to {new_status}.')
    return redirect('admin_order_detail', order_id=order_id)

@user_passes_test(is_admin, login_url='/login/')
def admin_coupons(request):
    coupons = Coupon.objects.all()
    return render(request, 'store/admin/coupons.html', {'coupons': coupons})


@user_passes_test(is_admin, login_url='/login/')
def admin_add_coupon(request):
    form = CouponForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Coupon created.')
        return redirect('admin_coupons')
    return render(request, 'store/admin/coupon_form.html', {'form': form, 'action': 'Add'})


@user_passes_test(is_admin, login_url='/login/')
def admin_edit_coupon(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    form = CouponForm(request.POST or None, instance=coupon)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Coupon updated.')
        return redirect('admin_coupons')
    return render(request, 'store/admin/coupon_form.html', {'form': form, 'action': 'Edit'})


@user_passes_test(is_admin, login_url='/login/')
def admin_delete_coupon(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    if request.method == 'POST':
        coupon.delete()
        messages.success(request, 'Coupon deleted.')
        return redirect('admin_coupons')
    return render(request, 'store/admin/confirm_delete.html', {'object': coupon, 'type': 'Coupon'})


@user_passes_test(is_admin, login_url='/login/')
def admin_banners(request):
    banners = Banner.objects.all()
    return render(request, 'store/admin/banners.html', {'banners': banners})


@user_passes_test(is_admin, login_url='/login/')
def admin_add_banner(request):
    form = BannerForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Banner created.')
        return redirect('admin_banners')
    return render(request, 'store/admin/banner_form.html', {'form': form, 'action': 'Add'})


@user_passes_test(is_admin, login_url='/login/')
def admin_edit_banner(request, pk):
    banner = get_object_or_404(Banner, pk=pk)
    form = BannerForm(request.POST or None, request.FILES or None, instance=banner)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Banner updated.')
        return redirect('admin_banners')
    return render(request, 'store/admin/banner_form.html', {'form': form, 'action': 'Edit'})


@user_passes_test(is_admin, login_url='/login/')
def admin_delete_banner(request, pk):
    banner = get_object_or_404(Banner, pk=pk)
    if request.method == 'POST':
        banner.delete()
        messages.success(request, 'Banner deleted.')
        return redirect('admin_banners')
    return render(request, 'store/admin/confirm_delete.html', {'object': banner, 'type': 'Banner'})


@user_passes_test(is_admin, login_url='/login/')
def admin_customers(request):
    customers = User.objects.filter(is_staff=False).annotate(
        order_count=Count('orders'),
        total_spend=Sum('orders__grand_total'),
    ).order_by('-date_joined')
    return render(request, 'store/admin/customers.html', {'customers': customers})


@user_passes_test(is_admin, login_url='/login/')
def admin_reviews(request):
    reviews = Review.objects.all().select_related('product', 'user')
    if request.method == 'POST':
        review_id = request.POST.get('review_id')
        action = request.POST.get('action')
        review = get_object_or_404(Review, id=review_id)
        if action == 'approve':
            review.is_approved = True
            review.save()
        elif action == 'reject':
            review.is_approved = False
            review.save()
        elif action == 'delete':
            review.delete()
        messages.success(request, f'Review {action}d.')
        return redirect('admin_reviews')
    return render(request, 'store/admin/reviews.html', {'reviews': reviews})

@require_POST
def contact_submit(request):
    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    phone = request.POST.get('phone', '').strip()
    subject = request.POST.get('subject', '').strip()
    message = request.POST.get('message', '').strip()

    if not all([name, email, subject, message]):
        return JsonResponse({'success': False, 'error': 'Please fill in all required fields.'})

    try:
        from django.core.mail import send_mail
        from django.conf import settings

        full_message = f"""
New Contact Form Submission — Cladly

Name: {name}
Email: {email}
Phone: {phone or 'Not provided'}
Subject: {subject}

Message:
{message}
"""
        send_mail(
            subject=f"Contact Form: {subject}",
            message=full_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.DEFAULT_FROM_EMAIL],
            fail_silently=False,
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'Could not send message. Please email us directly.'})
    
# COD DELIVERY ENABLE

def is_cod_allowed(pincode):
    """Check if COD is allowed for the given pincode."""
    if not pincode:
        return False
    return CODPincode.objects.filter(
        pincode=pincode.strip(),
        is_active=True
    ).exists()


@user_passes_test(is_admin, login_url='/login/')
def admin_cod_pincodes(request):
    pincodes = CODPincode.objects.all().order_by('pincode')
    form = CODPincodeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Pincode added to COD list.')
        return redirect('admin_cod_pincodes')
    return render(request, 'store/admin/cod_pincodes.html', {'pincodes': pincodes, 'form': form})


@user_passes_test(is_admin, login_url='/login/')
@require_POST
def admin_toggle_cod_pincode(request, pincode_id):
    p = get_object_or_404(CODPincode, id=pincode_id)
    p.is_active = not p.is_active
    p.save()
    messages.success(request, f'{p.pincode} COD {"enabled" if p.is_active else "disabled"}.')
    return redirect('admin_cod_pincodes')


@user_passes_test(is_admin, login_url='/login/')
@require_POST
def admin_delete_cod_pincode(request, pincode_id):
    p = get_object_or_404(CODPincode, id=pincode_id)
    p.delete()
    messages.success(request, 'Pincode removed from COD list.')
    return redirect('admin_cod_pincodes')


@user_passes_test(is_admin, login_url='/login/')
@require_POST
def admin_bulk_add_cod_pincodes(request):
    """Paste multiple pincodes at once, comma or newline separated."""
    raw = request.POST.get('bulk_pincodes', '')
    pincodes = [p.strip() for p in raw.replace(',', '\n').split('\n') if p.strip()]
    added = 0
    for pc in pincodes:
        if pc.isdigit() and len(pc) == 6:
            obj, created = CODPincode.objects.get_or_create(pincode=pc)
            if created:
                added += 1
    messages.success(request, f'{added} new pincode(s) added.')
    return redirect('admin_cod_pincodes')

def contact(request):
    return render(request, 'store/pages/contact.html')


def company(request):
    return render(request, 'store/pages/company.html')

def careers(request):
    return render(request, 'store/pages/careers.html')

def deliveryinfo(request):
    return render(request,'store/pages/deliveryinfo.html')

def privacypolicy(request):
    return render(request,'store/pages/privacypolicy.html')

def returns(request):
    return render(request,'store/pages/returns.html')