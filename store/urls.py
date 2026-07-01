from django.urls import path
from . import views

urlpatterns = [
    # ── Home
    path('', views.home, name='home'),

    # ── Auth
    path('register/', views.register_view, name='register'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<str:token>/', views.reset_password, name='reset_password'),

    # ── Products
    path('products/', views.product_list, name='product_list'),
    path('category/<slug:slug>/', views.category_products, name='category_products'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('search/', views.search, name='search'),
    path('search/suggestions/', views.search_suggestions, name='search_suggestions'),

    # ── Cart
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:item_id>/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/apply-coupon/', views.apply_coupon, name='apply_coupon'),
    path('cart/remove-coupon/', views.remove_coupon, name='remove_coupon'),

    # ── Wishlist
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/toggle/<int:product_id>/', views.toggle_wishlist, name='toggle_wishlist'),
    path('wishlist/move-to-cart/<int:product_id>/', views.move_to_cart, name='move_to_cart'),

    # ── Checkout & Orders
    path('checkout/', views.checkout, name='checkout'),
    path('place-order/', views.place_order, name='place_order'),
    path('order/success/<str:order_id>/', views.order_success, name='order_success'),
    path('payment/verify/', views.verify_payment, name='verify_payment'),
    path('payment/failed/<str:order_id>/', views.payment_failed, name='payment_failed'),
    path('orders/', views.my_orders, name='my_orders'),
    path('orders/<str:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<str:order_id>/cancel/', views.cancel_order, name='cancel_order'),
    path('orders/<str:order_id>/thank-you/', views.thank_you_card, name='thank_you_card'),

    # ── Profile
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),

    # ── Addresses
    path('addresses/', views.address_list, name='address_list'),
    path('addresses/add/', views.add_address, name='add_address'),
    path('addresses/<int:pk>/edit/', views.edit_address, name='edit_address'),
    path('addresses/<int:pk>/delete/', views.delete_address, name='delete_address'),
    path('addresses/<int:pk>/set-default/', views.set_default_address, name='set_default_address'),

    # ── Reviews
    path('product/<slug:slug>/review/', views.submit_review, name='submit_review'),

    # ── Notifications
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),

    # ── Admin Dashboard
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/products/', views.admin_products, name='admin_products'),
    path('admin-panel/products/add/', views.admin_add_product, name='admin_add_product'),
    path('admin-panel/products/<int:product_id>/edit/', views.admin_edit_product, name='admin_edit_product'),
    path('admin-panel/products/<int:pk>/delete/', views.admin_delete_product, name='admin_delete_product'),
    path('admin-panel/categories/', views.admin_categories, name='admin_categories'),
    path('admin-panel/categories/add/', views.admin_add_category, name='admin_add_category'),
    path('admin-panel/categories/<int:pk>/edit/', views.admin_edit_category, name='admin_edit_category'),
    path('admin-panel/categories/<int:pk>/delete/', views.admin_delete_category, name='admin_delete_category'),
    path('admin-panel/orders/', views.admin_orders, name='admin_orders'),
    path('admin-panel/orders/<str:order_id>/', views.admin_order_detail, name='admin_order_detail'),
    path('admin-panel/orders/<str:order_id>/update-status/', views.admin_update_order_status, name='admin_update_order_status'),
    path('admin-panel/orders/<str:order_id>/shipping-label/', views.admin_shipping_label, name='admin_shipping_label'),
    path('admin-panel/orders/<str:order_id>/invoice/', views.admin_invoice, name='admin_invoice'),
    path('admin-panel/coupons/', views.admin_coupons, name='admin_coupons'),
    path('admin-panel/coupons/add/', views.admin_add_coupon, name='admin_add_coupon'),
    path('admin-panel/coupons/<int:pk>/edit/', views.admin_edit_coupon, name='admin_edit_coupon'),
    path('admin-panel/coupons/<int:pk>/delete/', views.admin_delete_coupon, name='admin_delete_coupon'),
    path('admin-panel/banners/', views.admin_banners, name='admin_banners'),
    path('admin-panel/banners/add/', views.admin_add_banner, name='admin_add_banner'),
    path('admin-panel/banners/<int:pk>/edit/', views.admin_edit_banner, name='admin_edit_banner'),
    path('admin-panel/banners/<int:pk>/delete/', views.admin_delete_banner, name='admin_delete_banner'),
    path('admin-panel/customers/', views.admin_customers, name='admin_customers'),
    path('admin-panel/reviews/', views.admin_reviews, name='admin_reviews'),

    # COMAPNY CONTACT AND SUPPORT PAGES 
    path('company/', views.company, name='company'),
    path('careers/', views.careers, name='careers'),
    path('contact/', views.contact, name='contact'),
    path('contact/submit/', views.contact_submit, name='contact_submit'),
    path('privacypolicy/', views.privacypolicy, name='privacypolicy'),
    path('returns/', views.returns, name='returns'),
    path('deliveryinfo/', views.deliveryinfo, name='deliveryinfo'),




    #  ENABLE AND DISABLE THE COD 
    path('admin-panel/cod-pincodes/', views.admin_cod_pincodes, name='admin_cod_pincodes'),
    path('admin-panel/cod-pincodes/<int:pincode_id>/toggle/', views.admin_toggle_cod_pincode, name='admin_toggle_cod_pincode'),
    path('admin-panel/cod-pincodes/<int:pincode_id>/delete/', views.admin_delete_cod_pincode, name='admin_delete_cod_pincode'),
    path('admin-panel/cod-pincodes/bulk-add/', views.admin_bulk_add_cod_pincodes, name='admin_bulk_add_cod_pincodes'),
]
