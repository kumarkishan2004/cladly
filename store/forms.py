from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from .models import CODPincode, User, Address, Review, Product, Category, Coupon, Banner, ProductImage,ProductSize

FORM_CTRL = 'form-control'


def _add_classes(form):
    """Add form-control CSS class to all visible fields."""
    for field_name, field in form.fields.items():
        widget = field.widget
        if not isinstance(widget, (forms.CheckboxInput, forms.RadioSelect, forms.FileInput)):
            existing = widget.attrs.get('class', '')
            if FORM_CTRL not in existing:
                widget.attrs['class'] = (existing + ' ' + FORM_CTRL).strip()
    return form


class RegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Create password', 'class': FORM_CTRL}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm password', 'class': FORM_CTRL}))

    class Meta:
        model = User
        fields = ['full_name', 'email', 'mobile', 'password']
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'Your full name', 'class': FORM_CTRL}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email address', 'class': FORM_CTRL}),
            'mobile': forms.TextInput(attrs={'placeholder': '10-digit mobile number', 'class': FORM_CTRL}),
        }

    def clean_mobile(self):
        mobile = self.cleaned_data.get('mobile')
        if mobile and (not mobile.isdigit() or len(mobile) != 10):
            raise forms.ValidationError('Enter a valid 10-digit mobile number.')
        return mobile

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password')
        p2 = cleaned.get('confirm_password')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match.')
        return cleaned


class LoginForm(forms.Form):
    identifier = forms.CharField(
        label='Email or Mobile',
        widget=forms.TextInput(attrs={'placeholder': 'Email or mobile number', 'class': FORM_CTRL})
    )
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password', 'class': FORM_CTRL}))


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Your registered email', 'class': FORM_CTRL}))


class ResetPasswordForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'New password', 'class': FORM_CTRL}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm new password', 'class': FORM_CTRL}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('confirm_password'):
            raise forms.ValidationError('Passwords do not match.')
        return cleaned


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['full_name', 'mobile', 'profile_image']


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['name', 'mobile', 'address_line', 'college_name', 'hostel_name',
                  'room_number', 'city', 'state', 'pincode', 'is_default']
        widgets = {
            'address_line': forms.Textarea(attrs={'rows': 3, 'class': FORM_CTRL}),
            'name': forms.TextInput(attrs={'class': FORM_CTRL}),
            'mobile': forms.TextInput(attrs={'class': FORM_CTRL}),
            'college_name': forms.TextInput(attrs={'class': FORM_CTRL}),
            'city': forms.TextInput(attrs={'class': FORM_CTRL}),
            'state': forms.TextInput(attrs={'class': FORM_CTRL}),
            'pincode': forms.TextInput(attrs={'class': FORM_CTRL}),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'title', 'content', 'image']
        widgets = {
            'rating': forms.Select(
                choices=[(i, f'{i} Star{"s" if i > 1 else ""}') for i in range(1, 6)],
                attrs={'class': FORM_CTRL}
            ),
            'title': forms.TextInput(attrs={'class': FORM_CTRL, 'placeholder': 'Review title'}),
            'content': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Share your experience...', 'class': FORM_CTRL}),
        }


# Admin Forms
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'slug', 'category', 'description', 'material', 'color',
                  'original_price', 'selling_price', 'local_market_price','stock_quantity',
                   'styling_tips','is_active', 'is_new_arrival', 'is_best_seller', 'is_featured',
                  'delivery_days', 'tags']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'class': FORM_CTRL}),
            'tags': forms.TextInput(attrs={'placeholder': 'gold, earring, festive (comma-separated)', 'class': FORM_CTRL}),
            'name': forms.TextInput(attrs={'class': FORM_CTRL}),
            'slug': forms.TextInput(attrs={'class': FORM_CTRL}),
            'material': forms.TextInput(attrs={'class': FORM_CTRL}),
            'color': forms.TextInput(attrs={'class': FORM_CTRL}),
            'original_price': forms.NumberInput(attrs={'class': FORM_CTRL}),
            'selling_price': forms.NumberInput(attrs={'class': FORM_CTRL}),
            'local_market_price': forms.NumberInput(attrs={'class': FORM_CTRL, 'placeholder': 'e.g. 599'}),
            'styling_tips': forms.Textarea(attrs={'class': FORM_CTRL, 'rows': 4, 'placeholder': 'e.g. Pair with a floral kurta and jhumkas for a festive look...'}),
            'stock_quantity': forms.NumberInput(attrs={'class': FORM_CTRL}),
            'delivery_days': forms.NumberInput(attrs={'class': FORM_CTRL}),
            'category': forms.Select(attrs={'class': FORM_CTRL}),
        }

ProductSizeFormSet = forms.inlineformset_factory(
    Product,
    ProductSize,
    fields=['size_label', 'stock_quantity', 'order'],
    extra=5,
    can_delete=True,
    widgets={
        'size_label': forms.TextInput(attrs={'class': FORM_CTRL, 'placeholder': 'e.g. S, M, 2.2, 30'}),
        'stock_quantity': forms.NumberInput(attrs={'class': FORM_CTRL, 'min': 0}),
        'order': forms.NumberInput(attrs={'class': FORM_CTRL, 'min': 0}),
    }
)




class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'slug', 'image', 'description', 'is_active', 'order', 'gender']
        widgets = {
            'name': forms.TextInput(attrs={'class': FORM_CTRL}),
            'slug': forms.TextInput(attrs={'class': FORM_CTRL}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': FORM_CTRL}),
            'order': forms.NumberInput(attrs={'class': FORM_CTRL}),
            'gender': forms.Select(attrs={'class': FORM_CTRL}),
        }


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ['code', 'description', 'discount_type', 'discount_value',
                  'minimum_order_value', 'max_uses', 'start_date', 'expiry_date',
                  'is_active', 'for_new_users_only']
        widgets = {
            'code': forms.TextInput(attrs={'class': FORM_CTRL, 'style': 'text-transform:uppercase;letter-spacing:2px;font-weight:700;'}),
            'description': forms.TextInput(attrs={'class': FORM_CTRL}),
            'discount_type': forms.Select(attrs={'class': FORM_CTRL}),
            'discount_value': forms.NumberInput(attrs={'class': FORM_CTRL}),
            'minimum_order_value': forms.NumberInput(attrs={'class': FORM_CTRL}),
            'max_uses': forms.NumberInput(attrs={'class': FORM_CTRL}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': FORM_CTRL}),
            'expiry_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': FORM_CTRL}),
        }


class BannerForm(forms.ModelForm):
    class Meta:
        model = Banner
        fields = ['title', 'subtitle', 'image', 'mobile_image', 'link',
                  'banner_type', 'is_active', 'order', 'start_date', 'end_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': FORM_CTRL}),
            'subtitle': forms.TextInput(attrs={'class': FORM_CTRL}),
            'link': forms.TextInput(attrs={'class': FORM_CTRL}),
            'banner_type': forms.Select(attrs={'class': FORM_CTRL}),
            'order': forms.NumberInput(attrs={'class': FORM_CTRL}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': FORM_CTRL}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': FORM_CTRL}),
        }


# FOR COD DELIVERY ENABLE

class CODPincodeForm(forms.ModelForm):
    class Meta:
        model = CODPincode
        fields = ['pincode', 'area_note', 'is_active']
        widgets = {
            'pincode': forms.TextInput(attrs={'class': FORM_CTRL, 'placeholder': 'e.g. 751001', 'maxlength': 10}),
            'area_note': forms.TextInput(attrs={'class': FORM_CTRL, 'placeholder': 'Optional — e.g. Patia, Bhubaneswar'}),
        }