from django.urls import path
from .views import CreateUserView, LoginView, CourseSearchView, CurrentUserView

urlpatterns = [
    path('auth/register/', CreateUserView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/me/', CurrentUserView.as_view(), name='current-user'),
    path('courses/search/', CourseSearchView.as_view(), name='course-search'),
] 