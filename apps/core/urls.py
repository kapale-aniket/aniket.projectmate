from django.urls import path
from .views import HomeView, AboutView, ContactView, ProjectView, SearchView, ThemeToggleView
from .chatbot_views import chatbot_ask

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("about/", AboutView.as_view(), name="about"),
    path("project/", ProjectView.as_view(), name="project"),
    path("contact/", ContactView.as_view(), name="contact"),
    path("search/", SearchView.as_view(), name="search"),
    path("theme/toggle/", ThemeToggleView.as_view(), name="theme_toggle"),
    path("chatbot/ask/", chatbot_ask, name="chatbot_ask"),
]
