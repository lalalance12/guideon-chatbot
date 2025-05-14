# filepath: c:\Users\Asus\Desktop\guideon-chatbot\backend\api\urls.py
from django.urls import path
# Updated view import
from .views import CreateUserView, ContextRetrieverView, LoginView, CourseSearchView, CurrentUserView, SemanticCourseSearchView

urlpatterns = [
    # path('users/', CreateUserView.as_view(), name='create_user'),
    # Updated path and name
    path('auth/register/', CreateUserView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/me/', CurrentUserView.as_view(), name='current-user'),
    path('courses/search/', CourseSearchView.as_view(), name='search-courses'),
    path('retrieve-context/', ContextRetrieverView.as_view(), name='retrieve-context'),
    path('course-search/', SemanticCourseSearchView.as_view(), name='course-search'),
]