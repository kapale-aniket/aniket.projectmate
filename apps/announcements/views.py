from django.views.generic import ListView, DetailView
from django.utils import timezone
from .models import Announcement


class AnnouncementListView(ListView):
    model = Announcement
    template_name = "pages/announcements.html"
    context_object_name = "announcements"
    paginate_by = 10

    def get_queryset(self):
        qs = Announcement.objects.visible()
        cat = self.request.GET.get("category")
        q = self.request.GET.get("q")
        if cat:
            qs = qs.filter(category=cat)
        if q:
            qs = qs.filter(title__icontains=q)
        return qs


class AnnouncementDetailView(DetailView):
    model = Announcement
    template_name = "pages/announcement_detail.html"
    context_object_name = "announcement"
    slug_field = "slug"

    def get_queryset(self):
        return Announcement.objects.visible()

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        Announcement.objects.filter(pk=obj.pk).update(views=obj.views + 1)
        return obj
