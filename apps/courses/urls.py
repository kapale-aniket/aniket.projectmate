from django.urls import path
from .views import PaidCourseListView, PaidCourseDetailView, EnrollCourseView

app_name = "courses"

urlpatterns = [
    path("", PaidCourseListView.as_view(), name="list"),
    path("<slug:slug>/", PaidCourseDetailView.as_view(), name="detail"),
    path("<slug:slug>/enroll/", EnrollCourseView.as_view(), name="enroll"),
]
