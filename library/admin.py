from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "role", "is_staff", "is_superuser")
    list_filter = ("role",)