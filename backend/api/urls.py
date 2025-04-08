from django.urls import path
from .views import CreateUserView, PathwayGeneratorView

urlpatterns = [
    path('users/', CreateUserView.as_view(), name='create_user'),
    path('generate-pathway/', PathwayGeneratorView.as_view(), name='generate-pathway'),
]