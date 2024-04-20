from django.urls import re_path

from . import views

app_name = 'wordle'

urlpatterns = [
  re_path(r'^$', views.main),
  re_path(r'^guess$', views.guess, name='guess'),
]
