from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *
from django.contrib import messages

# admin.site.register(CustomUser, UserAdmin)

@admin.register(CustomUser)
class UserAdmin(UserAdmin):
    list_display = ('id', 'username', 'email', 'bunq_api_key', 'bunq_context', 'first_name', 'last_name',  'is_staff', )

     # Fields to include in the admin add/edit forms
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Custom Fields', {'fields': ('first_name', 'last_name',  )}),  # Add your custom fields here
    )
    
    # Fields to include when adding a new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'organization', 'is_staff', 'is_active'),
        }),
    )

    # Make the admin searchable by email and username
    search_fields = ('email', 'username')
    ordering = ('email',)



