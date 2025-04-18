# filepath: c:\Users\Asus\Desktop\guideon-chatbot\backend\api\urls.py
from django.urls import path
# Updated view import
from .views import CreateUserView, ContextRetrieverView

urlpatterns = [
    path('users/', CreateUserView.as_view(), name='create_user'),
    # Updated path and name
    path('retrieve-context/', ContextRetrieverView.as_view(), name='retrieve-context'),
]