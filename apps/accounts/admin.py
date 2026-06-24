from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "extension")
    list_filter = ("role", "extension")
    search_fields = ("user__username", "user__email", "extension__name")
