from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator


# Create your models here.
# Создание модели 'Product'.
class Product(models.Model):
    seller = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=100)
    price = models.FloatField()
    file = models.FileField(upload_to="uploads")
    total_sales_amount = models.FloatField(default=0)
    total_sales = models.IntegerField(default=0)
    total_ratings = models.IntegerField(default=0)
    total_rating_value = models.FloatField(default=0.0)
    reviewed_by = models.ManyToManyField(User, related_name='reviewed_products', blank=True)

    def reviewed_by_user(self, user):
        return user in self.reviewed_by.all()

    def calculate_average_rating(self):
        if self.total_ratings == 0:
            return 0.0
        return self.total_rating_value / self.total_ratings

    @property
    def average_rating(self):
        return self.calculate_average_rating()

    @average_rating.setter
    def average_rating(self, value):
        pass

    def __str__(self):
        return self.name


# Создание модели 'OrderDetail'.
class OrderDetail(models.Model):
    customer_email = models.EmailField()
    products = models.ManyToManyField(Product)
    amount = models.FloatField()
    stripe_payment_intent = models.CharField(max_length=200)
    has_paid = models.BooleanField(default=False)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now_add=True)
    product_rating = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(5)])


# Создание модели 'CartItem'.
class CartItem(models.Model):
    cart = models.ForeignKey('Cart', related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)


# Создание модели 'Cart'.
class Cart(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    total = models.FloatField(default=0)

    @classmethod
    def get_cart(cls, customer):
        cart, created = cls.objects.get_or_create(customer=customer)
        return cart