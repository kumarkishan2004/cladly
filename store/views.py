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
from .email_utils import send_welcome_email, send_welcome_back_email, send_password_reset_email
from .password_reset_tokens import generate_reset_token, verify_reset_token, delete_reset_token
from .otp_utils import (
    generate_otp, send_otp_email, store_otp, verify_otp,
    delete_otp, increment_otp_attempts, get_otp_attempts, clear_otp_attempts
)
from .models import (
    User, Category, Product, ProductImage, Address, Cart, Wishlist,
    Order, OrderItem, OrderStatusHistory, Coupon, Review, Banner,
    Notification, RecentlyViewed
)
from .forms import (
    RegistrationForm, LoginForm, ForgotPasswordForm, ResetPasswordForm,
    ProfileEditForm, AddressForm, ReviewForm, ProductForm, CategoryForm,
    CouponForm, BannerForm
)


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
    delivery = 0 if subtotal >= 499 else 49
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
            # Send OTP before logging in
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
    product = get_object_or_404(Product, id=product_id, is_active=True)
    qty = int(request.POST.get('quantity', 1))

    if product.stock_status == 'out_of_stock':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Out of stock'})
        messages.error(request, 'This product is out of stock.')
        return redirect(request.META.get('HTTP_REFERER', 'cart'))

    if request.user.is_authenticated:
        item, created = Cart.objects.get_or_create(user=request.user, product=product)
    else:
        if not request.session.session_key:
            request.session.create()
        item, created = Cart.objects.get_or_create(
            session_key=request.session.session_key, product=product
        )

    if not created:
        item.quantity += qty
    else:
        item.quantity = qty
    item.save()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        cart_count = get_cart_items(request).count()
        return JsonResponse({'success': True, 'message': 'Added to cart!', 'cart_count': cart_count})

    messages.success(request, f'"{product.name}" added to cart!')
    return redirect(request.META.get('HTTP_REFERER', 'cart'))


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
    cart_items = get_cart_items(request)
    if not cart_items.exists():
        messages.warning(request, 'Your cart is empty.')
        return redirect('cart')

    coupon = _get_session_coupon(request)
    totals = calculate_cart_totals(cart_items, coupon)
    addresses = Address.objects.filter(user=request.user)
    address_form = AddressForm()

    return render(request, 'store/orders/checkout.html', {
        'cart_items': cart_items,
        'addresses': addresses,
        'address_form': address_form,
        'coupon': coupon,
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
    coupon = _get_session_coupon(request)
    totals = calculate_cart_totals(cart_items, coupon)

    # Create order
    order = Order.objects.create(
        user=request.user,
        address=address,
        delivery_name=address.name,
        delivery_mobile=address.mobile,
        delivery_address=address.address_line,
        delivery_college=address.college_name,
        delivery_hostel=address.hostel_name,
        delivery_room=address.room_number,
        delivery_city=address.city,
        delivery_pincode=address.pincode,
        payment_method=payment_method,
        coupon=coupon,
        coupon_code=coupon.code if coupon else '',
        expected_delivery=date.today() + timedelta(days=1),
        **totals,
    )

    # Create order items + reduce stock
    for item in cart_items:
        img = item.product.primary_image()
        OrderItem.objects.create(
            order=order,
            product=item.product,
            product_name=item.product.name,
            product_image=img.image.url if img and img.image else '',
            quantity=item.quantity,
            price=item.product.selling_price,
            original_price=item.product.original_price,
        )
        # Reduce stock
        item.product.stock_quantity = max(0, item.product.stock_quantity - item.quantity)
        item.product.update_stock_status()

    # Increment coupon usage
    if coupon:
        coupon.used_count += 1
        coupon.save()
        request.session.pop('coupon_id', None)

    # Clear cart
    cart_items.delete()

    # Status history
    OrderStatusHistory.objects.create(order=order, status='placed', note='Order placed successfully.')

    # Notification
    Notification.objects.create(
        user=request.user,
        title='Order Placed!',
        message=f'Your order {order.order_id} has been placed. Expected delivery: tomorrow.',
        notif_type='order',
        link=f'/orders/{order.order_id}/',
    )

    return redirect('order_success', order_id=order.order_id)


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
    if order.status in ['placed', 'confirmed']:
        order.status = 'cancelled'
        order.save()
        # Restore stock
        for item in order.items.all():
            if item.product:
                item.product.stock_quantity += item.quantity
                item.product.update_stock_status()
        OrderStatusHistory.objects.create(order=order, status='cancelled', note='Cancelled by customer.')
        Notification.objects.create(
            user=request.user,
            title='Order Cancelled',
            message=f'Your order {order.order_id} has been cancelled.',
            notif_type='order',
        )
        messages.success(request, 'Order cancelled successfully.')
    else:
        messages.error(request, 'This order cannot be cancelled.')
    return redirect('order_detail', order_id=order_id)


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
    return render(request, 'store/user/profile.html', {
        'orders_count': orders_count,
        'wishlist_count': wishlist_count,
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
    form = ProductForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        product = form.save()
        images = request.FILES.getlist('images')
        for i, img in enumerate(images):
            ProductImage.objects.create(product=product, image=img, is_primary=(i == 0), order=i)
        messages.success(request, f'Product "{product.name}" added.')
        return redirect('admin_products')
    return render(request, 'store/admin/product_form.html', {'form': form, 'action': 'Add'})


@user_passes_test(is_admin, login_url='/login/')
def admin_edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        product = form.save()
        images = request.FILES.getlist('images')
        for i, img in enumerate(images):
            ProductImage.objects.create(product=product, image=img, order=product.images.count() + i)
        messages.success(request, f'Product "{product.name}" updated.')
        return redirect('admin_products')
    return render(request, 'store/admin/product_form.html', {
        'form': form, 'product': product, 'action': 'Edit'
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
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Category created.')
        return redirect('admin_categories')
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
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    paginator = Paginator(orders, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'store/admin/orders.html', {
        'orders': page,
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
