from django import template
from ..models import Genre
register = template.Library()


@register.inclusion_tag('movies/menu.html')
def menu():
    genres = Genre.objects.all()
    return {'genres':genres}