from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Category, Product, ProductImage, Address, Cart, Wishlist,
    Order, OrderItem, OrderStatusHistory, Coupon, Review, Banner,
    Notification, RecentlyViewed
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'full_name', 'mobile', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'date_joined')
    search_fields = ('email', 'full_name', 'mobile')
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('full_name', 'mobile', 'profile_image')}),
        ('Referral', {'fields': ('referral_code', 'referred_by', 'referral_credits')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'mobile', 'password1', 'password2'),
        }),
    )


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'selling_price', 'stock_quantity', 'stock_status', 'is_active')
    list_filter = ('category', 'is_active', 'is_new_arrival', 'is_best_seller', 'stock_status')
    search_fields = ('name', 'description', 'tags')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'order')
    prepopulated_fields = {'slug': ('name',)}


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'price', 'quantity', 'original_price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'delivery_name', 'grand_total', 'status', 'payment_method', 'placed_at')
    list_filter = ('status', 'payment_method', 'placed_at')
    search_fields = ('order_id', 'delivery_name', 'delivery_mobile')
    readonly_fields = ('order_id', 'placed_at')
    inlines = [OrderItemInline]


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'discount_value', 'used_count', 'max_uses', 'is_active', 'expiry_date')
    list_filter = ('is_active', 'discount_type')


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'banner_type', 'is_active', 'order')
    list_filter = ('banner_type', 'is_active')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'rating')


admin.site.register(Address)
admin.site.register(Cart)
admin.site.register(Wishlist)
admin.site.register(Notification)
