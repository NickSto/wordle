from django.conf.urls import url

from . import views

app_name = 'wordle'

urlpatterns = [
  url(r'^$', views.main),
  url(r'^guess$', views.guess, name='guess'),
]
