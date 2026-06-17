# 🛍️ Cladly — Premium Fashion Accessories Platform

A mobile-first, luxury fashion accessories e-commerce platform built with Django. Designed for college students and young women with same-day campus delivery, premium packaging, and elegant black & gold UI.

---

## ✨ Features

### Store
- **11 Product Categories**: Earrings, Ear Studs, Jhumkas, Pendants, Necklaces, Bangles, Bracelets, Rings, Hair Accessories, Combo Sets, Gift Sets
- **Live Search** with autocomplete suggestions
- **Product Galleries** with zoom and multiple images
- **Wishlist** — save and move to cart
- **Smart Cart** with coupon codes, free delivery threshold
- **Reviews & Ratings** — verified purchase reviews with photo uploads

### Orders
- **5-step order tracking**: Placed → Confirmed → Packed → Out for Delivery → Delivered
- **Multiple payment options**: Cash on Delivery, UPI, Online
- **Campus-aware delivery** with hostel/room number fields
- **Printable Thank You Card** with next-order coupon

### User Accounts
- Email + Mobile login
- Profile management with referral system
- Address book (multiple addresses, default address)
- Order history and notifications

### Admin Panel (`/admin-panel/`)
- **Dashboard**: Daily/Weekly/Monthly revenue, best sellers, stock alerts
- **Product Management**: Add/edit products with multiple images, auto-slug
- **Order Management**: Update status, notify customers automatically
- **Coupon Engine**: Flat/percentage coupons with expiry, usage limits
- **Banner Manager**: Hero sliders, flash sales, campaign banners
- **Customer Directory**: Order history, total spend per customer
- **Review Moderation**: Approve/hide/delete reviews

### Design
- **Luxury Black & Gold** theme
- **Mobile-first**, fully responsive
- **Smooth animations** and scroll-reveal effects
- **Sticky navbar** with mobile bottom navigation
- Google Fonts: DM Serif Display + DM Sans

---

## 🚀 Quick Start

### 1. Clone / Extract the project

```bash
cd cladly
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Seed sample data (categories + coupons + admin user)

```bash
python manage.py seed_data
```



To use custom credentials:
```bash
python manage.py seed_data --admin-email you@email.com --admin-password YourPass123
```

### 6. Create media and static dirs

```bash
mkdir -p media staticfiles
python manage.py collectstatic --noinput
```

### 7. Start the development server

```bash
python manage.py runserver
```

Open: **http://127.0.0.1:8000/**

---

## 📁 Project Structure

```
cladly/
├── cladly/                    # Django project config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── store/                     # Main application
│   ├── models.py              # All database models
│   ├── views.py               # All views
│   ├── urls.py                # URL routing
│   ├── forms.py               # Form classes
│   ├── admin.py               # Django admin registration
│   ├── context_processors.py  # Cart/wishlist counts, categories
│   ├── apps.py
│   ├── management/
│   │   └── commands/
│   │       └── seed_data.py   # Sample data seeder
│   ├── static/store/
│   │   ├── css/main.css       # Luxury black & gold theme
│   │   └── js/main.js         # Cart, wishlist, slider, search JS
│   └── templates/store/
│       ├── home.html
│       ├── includes/product_card.html
│       ├── products/          # List, detail, category, search
│       ├── cart/
│       ├── orders/            # Checkout, success, detail, thank-you
│       ├── user/              # Profile, orders, wishlist, addresses
│       ├── auth/              # Register, login, forgot password
│       └── admin/             # Admin dashboard, all CRUD pages
├── templates/
│   └── base.html              # Main layout with navbar & footer
├── media/                     # User uploaded files (auto-created)
├── manage.py
└── requirements.txt
```

---

## 🔑 Key URLs

| URL | Description |
|-----|-------------|
| `/` | Homepage with hero slider, categories, products |
| `/products/` | All products with filters |
| `/category/<slug>/` | Category product listing |
| `/product/<slug>/` | Product detail with gallery |
| `/search/?q=...` | Search results |
| `/cart/` | Shopping cart |
| `/checkout/` | Checkout page |
| `/orders/` | My orders |
| `/profile/` | User profile |
| `/register/` | Create account |
| `/login/` | Login |
| `/admin-panel/` | Custom admin dashboard |
| `/django-admin/` | Django built-in admin |

---

## 🏷️ Sample Coupons (seeded automatically)

| Code | Discount | Min Order |
|------|----------|-----------|
| `WELCOME50` | ₹50 flat off | ₹299 |
| `CAMPUS20` | 20% off | ₹199 |
| `CLADLY10` | 10% off | No minimum |
| `FESTIVE100` | ₹100 flat off | ₹499 |

---

## 🗄️ Database Models

| Model | Description |
|-------|-------------|
| `User` | Custom user with mobile, referral system |
| `Category` | Product categories with slug |
| `Product` | Products with pricing, stock, images |
| `ProductImage` | Multiple images per product |
| `Address` | User delivery addresses (campus-aware) |
| `Cart` | Cart for both guest and logged-in users |
| `Wishlist` | User wishlist |
| `Order` | Orders with snapshot delivery address |
| `OrderItem` | Individual items within an order |
| `OrderStatusHistory` | Order status change log |
| `Coupon` | Flat/percentage coupons with expiry |
| `Review` | Product reviews with star ratings |
| `Banner` | Hero/sale/flash/campaign banners |
| `Notification` | User notifications |
| `RecentlyViewed` | Recently viewed products tracking |

---

## ⚙️ Production Checklist

Before deploying to production:

1. **Change secret key** in `settings.py`
2. Set `DEBUG = False`
3. Add your domain to `ALLOWED_HOSTS`
4. Configure **email SMTP** settings for password reset
5. Set up **PostgreSQL** instead of SQLite
6. Configure **AWS S3** or similar for media storage
7. Run `python manage.py collectstatic`
8. Set up **Nginx + Gunicorn** or use Railway/Render

---

## 📱 Adding Product Images

1. Login to admin panel 
2. Go to **Products → Add Product**
3. Fill in product details
4. Upload multiple images (first image becomes primary)
5. Set `Is Active` to make it visible on the store

---

## 🎨 Customisation

### Brand name
Replace `Cladly` in `templates/base.html`, `settings.py`, and `store/static/store/css/main.css`

### Colors
Edit CSS variables in `store/static/store/css/main.css`:
```css
:root {
  --gold: #C9A84C;        /* Primary gold */
  --gold-light: #E8C96A;  /* Hover gold */
  --black: #0A0A0A;       /* Background */
}
```

### Delivery charge logic
Edit `calculate_cart_totals()` in `store/views.py` — currently free above ₹499.

---

Built with Django 4.2 · SQLite · Mobile-first CSS · Vanilla JS
