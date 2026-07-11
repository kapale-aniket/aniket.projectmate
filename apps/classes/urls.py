from django.urls import path
from .views import FreeClassListView, FreeClassDetailView, RegisterClassView

app_name = "classes"

urlpatterns = [
    path("", FreeClassListView.as_view(), name="list"),
    path("<slug:slug>/", FreeClassDetailView.as_view(), name="detail"),
    path("<slug:slug>/register/", RegisterClassView.as_view(), name="register"),
]
