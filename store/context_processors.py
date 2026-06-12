from .models import Cart, Wishlist, Category, Notification


def cart_wishlist_count(request):
    cart_count = 0
    wishlist_count = 0
    notif_count = 0

    if request.user.is_authenticated:
        cart_count = Cart.objects.filter(user=request.user).count()
        wishlist_count = Wishlist.objects.filter(user=request.user).count()
        notif_count = Notification.objects.filter(user=request.user, is_read=False).count()
    else:
        session_key = request.session.session_key
        if session_key:
            cart_count = Cart.objects.filter(session_key=session_key).count()

    return {
        'cart_count': cart_count,
        'wishlist_count': wishlist_count,
        'notif_count': notif_count,
    }


def categories_list(request):
    categories = Category.objects.filter(is_active=True).order_by('order', 'name')
    return {'nav_categories': categories}
