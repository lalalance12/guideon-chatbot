# filepath: c:\Users\Asus\Desktop\guideon-chatbot\backend\api\urls.py
from django.urls import path
# Updated view import
from .views import (
    CompleteCourseView, SkillCoursesView,  # <-- add this import
    CreateUserView, ContextRetrieverView, LoginView, CurrentUserView, SemanticCourseSearchView, TakeCourseView,
    UserCoursesView,
)

urlpatterns = [
    # path('users/', CreateUserView.as_view(), name='create_user'),
    # Updated path and name
    path('auth/register/', CreateUserView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/me/', CurrentUserView.as_view(), name='current-user'),
    #path('courses/search/', CourseSearchView.as_view(), name='search-courses'),
    path('retrieve-context/', ContextRetrieverView.as_view(), name='retrieve-context'),
    path('course-search/', SemanticCourseSearchView.as_view(), name='course-search'),
    path('take-course/', TakeCourseView.as_view(), name='take-course'),
    path('user-courses/', UserCoursesView.as_view(), name='user-courses'),
    path('complete-course/', CompleteCourseView.as_view(), name='complete-course'),
    
    # Add the new route for skill courses
    path('skill-courses/', SkillCoursesView.as_view(), name='skill-courses'),
]