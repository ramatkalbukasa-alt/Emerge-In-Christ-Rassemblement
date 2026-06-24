from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import UserProfile

from .forms import ChurchExtensionForm
from .models import ChurchExtension


def admin_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        profile = getattr(request.user, "profile", None)
        if not profile or profile.role != UserProfile.Role.ADMIN:
            return redirect("dashboard:home")
        return view_func(request, *args, **kwargs)

    return wrapper


@admin_required
def extension_list(request):
    extensions = ChurchExtension.objects.all()
    return render(request, "churches/extension_list.html", {"extensions": extensions})


@admin_required
def extension_create(request):
    form = ChurchExtensionForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("churches:list")
    return render(request, "churches/extension_form.html", {"form": form, "title": "Nouvelle extension"})


@admin_required
def extension_update(request, slug):
    extension = get_object_or_404(ChurchExtension, slug=slug)
    form = ChurchExtensionForm(request.POST or None, instance=extension)
    if form.is_valid():
        form.save()
        return redirect("churches:list")
    return render(request, "churches/extension_form.html", {"form": form, "title": "Modifier extension"})
