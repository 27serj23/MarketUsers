from django import forms
from .models import Product
from django.contrib.auth.models import User


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'file']


# from django.contrib.auth.models import User
class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name']

        # добавление проверки соответствия паролей в процесс проверки формуляров

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password2 = cleaned_data.get('password2')

    # выше, использую self.cleaned_data['field_name'] вместо self.field_name, поскольку словарь cleaned_data содержит проверенные (в процессе проверки форм) и очищенные значения для всех полей формы.

        if password and password2 and password != password2:
            raise forms.ValidationError('Password fields do not match')

        return cleaned_data