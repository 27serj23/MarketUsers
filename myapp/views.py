from django.shortcuts import render, reverse, get_object_or_404, redirect
from .models import Product, OrderDetail, Cart, CartItem
from django.conf import settings
import stripe
from django.views.decorators.csrf import csrf_exempt
import json
from django.http import JsonResponse, HttpResponseNotFound
from .forms import ProductForm, UserRegistrationForm
from django.db.models import Sum, Q
import datetime
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F


# - Добавлена возможность для пользователей, прошедших проверку подлинности, добавлять товары в корзину.
# - Извлекает товар по идентификатору и создает или обновляет элемент корзины.
# - Увеличивает количество, если товар уже есть в корзине.
# - Обновляет общую стоимость корзины и возвращает ответ в формате JSON, подтверждающий добавление.
@login_required
def view_cart(request):
    stripe_publishable_key = settings.STRIPE_PUBLISHABLE_KEY
    cart = Cart.objects.get_or_create(customer=request.user)[0]
    return render(request, 'myapp/cart.html', {'cart': cart, 'stripe_publishable_key': stripe_publishable_key})


# Реализована функция добавления в корзину
# - Добавлена возможность для пользователей, прошедших проверку подлинности, добавлять товары в корзину.
# - Извлекает товар по идентификатору и создает или обновляет элемент корзины.
# - Увеличивает количество, если товар уже есть в корзине.
# - Обновляет общую стоимость корзины и возвращает ответ в формате JSON, подтверждающий добавление.
@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart, created = Cart.objects.get_or_create(customer=request.user)

    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)

    if not created:
        cart_item.quantity = F('quantity') + 1
        cart_item.save()

    cart.total = F('total') + product.price
    cart.save()

    return JsonResponse({'message': 'Item added to cart'})


# Реализована функция удаления из корзины
# - Добавлена возможность для пользователей, прошедших проверку подлинности, удалять товары из своей корзины.
# - Поиск товара по идентификатору и корзине пользователя.
# - Уменьшает количество, если товар есть в корзине, или удаляет товар, если количество достигает 0.
# - Обновляет общую стоимость корзины и возвращает ответ в формате JSON, подтверждающий удаление.
@login_required
def remove_from_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = Cart.objects.get(customer=request.user)

    cart_item = get_object_or_404(CartItem, cart=cart, product=product)
    if cart_item.quantity > 1:
        cart_item.quantity -= 1
        cart_item.save()
    else:
        cart_item.delete()

    cart.total -= product.price * cart_item.quantity
    cart.save()

    return JsonResponse({'message': 'Item removed from cart'})


# Отображать продукты и пользователя на странице индекса
#
# - Извлекает все продукты из базы данных.
# - Извлекает текущего пользователя из запроса.
# - Передает продукты и пользователя в шаблон "myapp/index.html" для отображения.
def index(request):
    products = Product.objects.all()
    user = request.user

    return render(request, "myapp/index.html", {'products': products, 'user': user})


# - Реализована функциональность сведений о продукте для отображения индивидуальной информации о продукте.
# - Извлекается продукт по идентификатору и передается в шаблон "myapp/detail.html".
# - Добавлен публикуемый ключ Stripe для обработки платежей.
def detail(request, id):
    product = Product.objects.get(id=id)
    stripe_publishable_key = settings.STRIPE_PUBLISHABLE_KEY

    return render(request, 'myapp/detail.html', {'product': product, 'stripe_publishable_key': stripe_publishable_key})


# - Добавлена функциональность для создания сеанса оформления заказа в Stripe для корзины пользователя.
# - Извлекает электронную почту пользователя и товары из корзины, создавая кампании для оформления заказа.
# - Использует транзакцию базы данных для обеспечения атомарности в процессе создания сеанса.
# - Возвращает ответ в формате JSON с информацией о сеансе оформления заказа.
def create_checkout_session(request):
    request_data = json.loads(request.body)
    email = request_data.get('email', '').strip()

    cart = Cart.get_cart(request.user)

    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Использую транзакцию базы данных для обеспечения атомарности
    with transaction.atomic():
        line_items = [
            {
                'price_data': {
                    'currency': 'gbp',
                    'product_data': {
                        'name': item.product.name,
                    },
                    'unit_amount': int(item.product.price * 100)
                },
                'quantity': item.quantity,
            }
            for item in cart.items.all()
        ]

        checkout_session = stripe.checkout.Session.create(
            customer_email=email,
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=request.build_absolute_uri(reverse('success')) + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.build_absolute_uri(reverse('failed')),
        )

        # Создаем заказ для каждого элемента корзины
        for item in cart.items.all():
            order = OrderDetail.objects.create(
                customer_email=email,
                amount=item.product.price * item.quantity,
                stripe_payment_intent='dummy_payment_intent',
                has_paid=False
            )
            order.products.add(item.product)

        # Очищаем корзину после обработки
        cart.delete()

    return JsonResponse({'sessionId': checkout_session.id})


# - Извлекает идентификатор сеанса Stripe из запроса и проверяет его.
# - Извлекает соответствующий заказ, используя намерение оплаты из сеанса Stripe.
# - Помечает заказ как оплаченный и обновляет статистику продаж продукта.
# - Отображает страницу успешного выполнения платежа с подробной информацией о заказе.
def payment_success_view(request):
    session_id = request.GET.get('session_id')
    if session_id is None:
        return HttpResponseNotFound()

    stripe.api_key = settings.STRIPE_SECRET_KEY
    session = stripe.checkout.Session.retrieve(session_id)
    order = get_object_or_404(OrderDetail, stripe_payment_intent=session.payment_intent)

    order.has_paid = True

    # обновление статистики продаж продукта
    product = Product.objects.get(id=order.product.id)
    product.total_sales_amount += int(product.price)
    product.total_sales += 1
    product.save()

    order.save()

    return render(request, 'myapp/payment_success.html', {'order': order})


# - Добавлена функциональность для отображения страницы сбоев платежей.
# - Возвращает шаблон "myapp/failed.html" для пользователей, которые сталкиваются с проблемами при оплате.
def payment_failed_view(request):
    return render(request, 'myapp/failed.html')


# - Реализована возможность для пользователей, вошедших в систему, создавать новые продукты.
# - - Обрабатывает запросы POST с помощью "Формы продукта" для сохранения нового продукта.
# - Устанавливает в поле "продавец" имя текущего пользователя перед сохранением продукта.
# - Перенаправляет на индексную страницу после успешного создания.
# - Отображает шаблон "myapp/create_product.html" с формой для запросов GET.
@login_required
def create_product(request):
    if request.method == "POST":
        product_form = ProductForm(request.POST, request.FILES)
        if product_form.is_valid():
            new_product = product_form.save(commit=False)
            new_product.seller = request.user
            new_product.save()
            return redirect('index')

    product_form = ProductForm()
    return render(request, 'myapp/create_product.html', {'product_form': product_form})


# - Добавлена возможность для пользователей, прошедших проверку подлинности, редактировать свои товары.
# - Проверяется, является ли пользователь продавцом или суперпользователем, прежде чем разрешить внесение изменений.
# - Обрабатывает запросы POST на обновление сведений о товаре через `Форму товара`.
# - При успешном обновлении выполняется перенаправление на указательную страницу.
# - Отображается шаблон "myapp/product_edit.html" с формой продукта для запросов GET.
@login_required
def product_edit(request, id):
    product = Product.objects.get(id=id)

    if not (request.user.is_superuser or product.seller == request.user):
        return redirect('invalid')

    product_form = ProductForm(request.POST or None, request.FILES or None, instance=product)

    if request.method == "POST":
        if product_form.is_valid():
            product_form.save()
            return redirect('index')

    return render(request, 'myapp/product_edit.html', {'product_form': product_form, 'product': product})


# - Добавлена возможность для пользователей, прошедших проверку подлинности, удалять свои продукты.
# - Проверяется, является ли пользователь продавцом или суперпользователем, прежде чем разрешить удаление.
# - Обрабатываются запросы POST на удаление продукта и перенаправление на указанную страницу.
# - Отображает страницу подтверждения для получения запросов на подтверждение удаления.
@login_required
def product_delete(request, id):
    product = Product.objects.get(id=id)

    if not (request.user.is_superuser or product.seller == request.user):
        return redirect('invalid')

    if request.method == "POST":
        product.delete()
        return redirect('index')

    return render(request, 'myapp/delete.html', {'product': product})


#
@login_required
def dashboard(request):
    if request.user.is_superuser:
        products = Product.objects.all()
    else:
        products = Product.objects.filter(seller=request.user)

    for product in products:
        orders = OrderDetail.objects.filter(products=product)
        product.total_orders = orders.count()
        product.total_revenue = product.price * orders.count()
        product.random_rating = product.average_rating

    return render(request, 'myapp/dashboard.html', {'products': products})


# registration view
def register(request):
    if request.method == "POST":
        user_form = UserRegistrationForm(request.POST)

        # saving data and adding passwords, then saving user
        new_user = user_form.save(commit=False)
        new_user.set_password(user_form.cleaned_data['password'])
        new_user.save()
        return redirect('index')

    user_form = UserRegistrationForm()
    return render(request, 'myapp/register.html', {'user_form': user_form})


# недопустимый view (например, при попытке доступа к операциям редактирования или удаления продуктов других продавцов)
def invalid(request):
    return render(request, 'myapp/invalid.html')


# view моих покупок
@login_required
def my_purchases(request):
    if request.user.is_superuser:
        orders = OrderDetail.objects.all()
    else:
        orders = OrderDetail.objects.filter(customer_email=request.user.email)

    return render(request, 'myapp/purchases.html', {'orders': orders})


# просмотр панели мониторинга продаж
@login_required
def sales(request):
    if request.user.is_superuser:
        orders = OrderDetail.objects.all()
    else:
        orders = OrderDetail.objects.filter(products__seller=request.user)

    total_sales = orders.aggregate(Sum('amount'))
    user = request.user

    # расчет суммы продаж за прошлый год (за последние 365 дней)
    last_year = datetime.date.today() - datetime.timedelta(days=365)
    last_year_orders = orders.filter(created_on__gt=last_year)
    yearly_sales = last_year_orders.aggregate(Sum('amount'))

    # расчет суммы продаж за последние 30 дней
    last_month = datetime.date.today() - datetime.timedelta(days=30)
    last_month_orders = orders.filter(created_on__gt=last_month)
    monthly_sales = last_month_orders.aggregate(Sum('amount'))

    # расчет суммы продаж за последние 7 дней
    last_week = datetime.date.today() - datetime.timedelta(days=7)
    last_week_orders = orders.filter(created_on__gt=last_week)
    weekly_sales = last_week_orders.aggregate(Sum('amount'))

    # ежедневная сумма за каждый день за последние 30 дней
    daily_sales_sums = orders.values('created_on__date').order_by('created_on__date').annotate(sum=Sum('amount'))

    # сумма продаж за продукт (аналогично приведенному выше, будет создан список объектов)
    product_sales_sums = orders.values('products__name').order_by('products__name').annotate(sum=Sum('amount'))

    return render(request, 'myapp/sales.html',
                  {'orders': orders, 'total_sales': total_sales, 'user': user, 'yearly_sales': yearly_sales,
                   'monthly_sales': monthly_sales, 'weekly_sales': weekly_sales, 'daily_sales_sums': daily_sales_sums,
                   'product_sales_sums': product_sales_sums})


# просмотр заказов / оценок
def orders(request):
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        rating = request.POST.get('rating')
        user = request.user

        order_detail = OrderDetail.objects.get(id=order_id)
        order_detail.product_rating = rating
        order_detail.save()

        for product in order_detail.products.all():
            product.total_ratings += 1
            product.total_rating_value += int(rating)
            product.reviewed_by.add(user)
            product.save()

        for product in Product.objects.all():
            product.average_rating = product.calculate_average_rating()
            product.save()

        return redirect('orders')

    purchases = OrderDetail.objects.filter(customer_email=request.user.email)
    return render(request, 'myapp/orders.html', {'purchases': purchases})


def search_bar(request):
    if request.method == "POST":
        query = request.POST.get('search')
        print(query)
        products = Product.objects.filter(Q(name__icontains=query) | Q(description__icontains=query))
        return render(request, 'myapp/search.html', {'products': products, "query": query})
    else:
        return render(request, 'myapp/index.html')
