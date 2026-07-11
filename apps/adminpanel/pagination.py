"""Shared helpers for admin panel views."""
from django.core.paginator import Paginator

PAGE_SIZE = 10


def paginate_queryset(request, queryset, per_page=PAGE_SIZE, page_param="page"):
    """Return a Django Page object for the given queryset."""
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get(page_param) or 1)
