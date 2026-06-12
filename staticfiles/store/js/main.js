// ═══════════════════════════════════════════
// CLADLY — Main JavaScript
// ═══════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  initHeroSlider();
  initSearchSuggestions();
  initCartButtons();
  initWishlistButtons();
  initGallery();
  initCountdown();
  initToasts();
  initQtyControls();
  initPaymentSelect();
  initAddressSelect();
});

// ─── CSRF helper ───────────────────────────
function getCsrf() {
  return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
         document.cookie.split('; ').find(r => r.startsWith('csrftoken='))?.split('=')[1] || '';
}

function post(url, data = {}) {
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = url;
  form.innerHTML = `<input name="csrfmiddlewaretoken" value="${getCsrf()}">`;
  Object.entries(data).forEach(([k, v]) => {
    const i = document.createElement('input');
    i.name = k; i.value = v;
    form.appendChild(i);
  });
  document.body.appendChild(form);
  form.submit();
}

async function ajaxPost(url, data = {}) {
  const formData = new FormData();
  formData.append('csrfmiddlewaretoken', getCsrf());
  Object.entries(data).forEach(([k, v]) => formData.append(k, v));
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
    body: formData,
  });
  return res.json();
}

// ─── Toast Notifications ───────────────────
function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container') || (() => {
    const el = document.createElement('div');
    el.id = 'toast-container';
    el.className = 'toast-container';
    document.body.appendChild(el);
    return el;
  })();

  const icons = { success: '✓', error: '✕', info: 'ℹ', warning: '⚠' };
  const colors = { success: '#50B878', error: '#E05050', info: '#50A0E0', warning: '#E0A050' };

  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.style.borderLeftColor = colors[type] || colors.success;
  toast.innerHTML = `<span style="color:${colors[type]}">${icons[type]}</span> ${message}`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'slideIn 0.3s ease reverse';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function initToasts() {
  // Auto-display Django messages
  document.querySelectorAll('.django-message').forEach(el => {
    const type = el.dataset.type || 'info';
    showToast(el.textContent.trim(), type);
  });
}

// ─── Hero Slider ───────────────────────────
function initHeroSlider() {
  const slides = document.querySelectorAll('.hero-slide');
  const dots = document.querySelectorAll('.hero-dot');
  if (!slides.length) return;

  let current = 0;
  let timer;

  function goTo(n) {
    slides[current].classList.remove('active');
    dots[current]?.classList.remove('active');
    current = (n + slides.length) % slides.length;
    slides[current].classList.add('active');
    dots[current]?.classList.add('active');
  }

  function next() { goTo(current + 1); }
  goTo(0);
  timer = setInterval(next, 4500);

  dots.forEach((dot, i) => {
    dot.addEventListener('click', () => {
      clearInterval(timer);
      goTo(i);
      timer = setInterval(next, 4500);
    });
  });

  // Touch swipe
  const slider = document.querySelector('.hero-slider');
  if (slider) {
    let startX;
    slider.addEventListener('touchstart', e => startX = e.touches[0].clientX, { passive: true });
    slider.addEventListener('touchend', e => {
      const diff = startX - e.changedTouches[0].clientX;
      if (Math.abs(diff) > 50) {
        clearInterval(timer);
        goTo(diff > 0 ? current + 1 : current - 1);
        timer = setInterval(next, 4500);
      }
    });
  }
}

// ─── Search Suggestions ────────────────────
function initSearchSuggestions() {
  const input = document.getElementById('search-input');
  const box = document.getElementById('search-suggestions');
  if (!input || !box) return;

  let debounce;

  input.addEventListener('input', () => {
    clearTimeout(debounce);
    const q = input.value.trim();
    if (q.length < 2) { box.classList.remove('visible'); return; }
    debounce = setTimeout(async () => {
      try {
        const res = await fetch(`/search/suggestions/?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        renderSuggestions(data.suggestions);
      } catch {}
    }, 200);
  });

  document.addEventListener('click', e => {
    if (!input.contains(e.target) && !box.contains(e.target)) {
      box.classList.remove('visible');
    }
  });

  function renderSuggestions(items) {
    if (!items.length) { box.classList.remove('visible'); return; }
    box.innerHTML = items.map(s => `
      <a href="/product/${s.slug}/" class="suggestion-item">
        ${s.image ? `<img src="${s.image}" class="suggestion-thumb" alt="">` : '<div class="suggestion-thumb"></div>'}
        <div>
          <div class="suggestion-name">${s.name}</div>
          <div class="suggestion-price">₹${parseFloat(s.price).toFixed(0)}</div>
        </div>
      </a>
    `).join('');
    box.classList.add('visible');
  }
}

// ─── Cart Buttons ──────────────────────────
function initCartButtons() {
  document.querySelectorAll('[data-add-cart]').forEach(btn => {
    btn.addEventListener('click', async function(e) {
      e.preventDefault();
      const productId = this.dataset.addCart;
      const qty = this.dataset.qty || 1;
      const original = this.textContent;

      this.disabled = true;
      this.textContent = '...';

      try {
        const data = await ajaxPost(`/cart/add/${productId}/`, { quantity: qty });
        if (data.success) {
          showToast('Added to cart! 🛍️', 'success');
          // Update cart count badge
          document.querySelectorAll('.cart-count-badge').forEach(el => {
            el.textContent = data.cart_count;
            el.style.display = data.cart_count > 0 ? 'flex' : 'none';
          });
          this.textContent = '✓ Added';
          setTimeout(() => { this.textContent = original; this.disabled = false; }, 1500);
        } else {
          showToast(data.message || 'Out of stock', 'error');
          this.textContent = original;
          this.disabled = false;
        }
      } catch {
        showToast('Something went wrong', 'error');
        this.textContent = original;
        this.disabled = false;
      }
    });
  });
}

// ─── Wishlist Buttons ──────────────────────
function initWishlistButtons() {
  document.querySelectorAll('[data-wishlist]').forEach(btn => {
    btn.addEventListener('click', async function(e) {
      e.preventDefault();
      // If not logged in, redirect
      if (this.dataset.guest === 'true') {
        window.location.href = '/login/?next=' + encodeURIComponent(window.location.pathname);
        return;
      }
      const productId = this.dataset.wishlist;
      try {
        const data = await ajaxPost(`/wishlist/toggle/${productId}/`);
        const isAdded = data.added;
        this.classList.toggle('active', isAdded);
        this.textContent = isAdded ? '♥' : '♡';
        showToast(isAdded ? 'Added to wishlist ♥' : 'Removed from wishlist', isAdded ? 'success' : 'info');
        document.querySelectorAll('.wishlist-count-badge').forEach(el => {
          el.textContent = data.wishlist_count;
        });
      } catch {}
    });
  });
}

// ─── Product Gallery ───────────────────────
function initGallery() {
  const mainImg = document.getElementById('gallery-main-img');
  if (!mainImg) return;

  document.querySelectorAll('.gallery-thumb').forEach(thumb => {
    thumb.addEventListener('click', function() {
      mainImg.src = this.dataset.full;
      document.querySelectorAll('.gallery-thumb').forEach(t => t.classList.remove('active'));
      this.classList.add('active');
    });
  });

  // Zoom on click
  mainImg.parentElement?.addEventListener('click', function() {
    const overlay = document.createElement('div');
    overlay.style.cssText = `
      position:fixed;inset:0;background:rgba(0,0,0,0.95);z-index:9999;
      display:flex;align-items:center;justify-content:center;cursor:zoom-out;
    `;
    const img = document.createElement('img');
    img.src = mainImg.src;
    img.style.cssText = 'max-width:90vw;max-height:90vh;object-fit:contain;border-radius:8px;';
    overlay.appendChild(img);
    overlay.addEventListener('click', () => overlay.remove());
    document.body.appendChild(overlay);
  });
}

// ─── Flash Sale Countdown ──────────────────
function initCountdown() {
  const el = document.getElementById('flash-countdown');
  if (!el) return;

  const endTime = new Date(el.dataset.end || Date.now() + 6 * 3600000);

  function update() {
    const diff = endTime - Date.now();
    if (diff <= 0) { el.innerHTML = '<span style="color:var(--black)">Sale Ended</span>'; return; }

    const h = Math.floor(diff / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    const s = Math.floor((diff % 60000) / 1000);

    el.innerHTML = `
      <div class="countdown-block"><div class="countdown-num">${String(h).padStart(2,'0')}</div><div class="countdown-label">hrs</div></div>
      <span class="countdown-sep">:</span>
      <div class="countdown-block"><div class="countdown-num">${String(m).padStart(2,'0')}</div><div class="countdown-label">min</div></div>
      <span class="countdown-sep">:</span>
      <div class="countdown-block"><div class="countdown-num">${String(s).padStart(2,'0')}</div><div class="countdown-label">sec</div></div>
    `;
  }
  update();
  setInterval(update, 1000);
}

// ─── Quantity Controls ─────────────────────
function initQtyControls() {
  document.querySelectorAll('.qty-control').forEach(ctrl => {
    const minus = ctrl.querySelector('.qty-minus');
    const plus = ctrl.querySelector('.qty-plus');
    const input = ctrl.querySelector('.qty-num');
    if (!input) return;

    minus?.addEventListener('click', () => {
      const v = parseInt(input.value) - 1;
      if (v >= (parseInt(input.min) || 1)) input.value = v;
      input.dispatchEvent(new Event('change'));
    });
    plus?.addEventListener('click', () => {
      const v = parseInt(input.value) + 1;
      const max = parseInt(input.max) || 99;
      if (v <= max) input.value = v;
      input.dispatchEvent(new Event('change'));
    });
  });

  // Cart page qty update
  document.querySelectorAll('.qty-num[data-cart-item]').forEach(input => {
    input.addEventListener('change', () => {
      const itemId = input.dataset.cartItem;
      post(`/cart/update/${itemId}/`, { quantity: input.value });
    });
  });
}

// ─── Payment Method Select ─────────────────
function initPaymentSelect() {
  document.querySelectorAll('.payment-option').forEach(opt => {
    opt.addEventListener('click', function() {
      document.querySelectorAll('.payment-option').forEach(o => o.classList.remove('selected'));
      this.classList.add('selected');
      const radio = this.querySelector('input[type=radio]');
      if (radio) radio.checked = true;
    });
  });
}

// ─── Address Select ────────────────────────
function initAddressSelect() {
  document.querySelectorAll('.address-card').forEach(card => {
    card.addEventListener('click', function() {
      document.querySelectorAll('.address-card').forEach(c => c.classList.remove('selected'));
      this.classList.add('selected');
      const radio = this.querySelector('input[type=radio]');
      if (radio) radio.checked = true;
      // Hide new address form
      const newForm = document.getElementById('new-address-form');
      if (newForm && this.dataset.id !== 'new') newForm.style.display = 'none';
    });
  });

  const addNewBtn = document.getElementById('add-new-address');
  const newForm = document.getElementById('new-address-form');
  if (addNewBtn && newForm) {
    addNewBtn.addEventListener('click', () => {
      document.querySelectorAll('.address-card').forEach(c => c.classList.remove('selected'));
      newForm.style.display = newForm.style.display === 'none' ? 'block' : 'none';
    });
  }
}

// ─── Scroll Reveal ─────────────────────────
const observer = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.style.opacity = '1';
      e.target.style.transform = 'translateY(0)';
      observer.unobserve(e.target);
    }
  });
}, { threshold: 0.1 });

document.querySelectorAll('.product-card, .category-card, .stat-card').forEach(el => {
  el.style.opacity = '0';
  el.style.transform = 'translateY(20px)';
  el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
  observer.observe(el);
});
