from django.urls import path
from .views import FeedbackCreateView, TestimonialListView

app_name = "feedback"

urlpatterns = [
    path("", FeedbackCreateView.as_view(), name="create"),
    path("testimonials/", TestimonialListView.as_view(), name="testimonials"),
]
