from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
import requests
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractUser):
    email = models.EmailField('email', unique=True)
    username = models.CharField(max_length=150, blank=True, null=True, unique=True)
    bunq_api_key = models.CharField(max_length=255, blank=True, null=True)
    bunq_context = models.JSONField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    objects = CustomUserManager()  # add this line

    def __str__(self):
        return self.email
    
    def get_bunq_id(self):
        """Get bunq id from context"""
        context = self.bunq_context
        user_id = context.get('session_context', {}).get('user_id')
        return user_id
    
    def get_session_token(self):
        """Get bunq session token"""
        context = self.bunq_context
        tok = context.get('session_context', {}).get('token')
        return tok

    def get_primary_account(self):
        user_id = self.get_bunq_id()        
        session_token = self.get_session_token()        
        url = f"https://public-api.sandbox.bunq.com/v1/user/{user_id}/monetary-account-bank"
        
        response = requests.get(url, headers={
            "User-Agent": "django-app", 
            "Content-Type": "application/json",
            "X-Bunq-Client-Authentication": session_token
            }).json()
        
        accounts = response.get('Response', [])
        for acc in accounts:
            acc_detail = next(iter(acc.values()))
            if acc_detail.get('status') == 'ACTIVE':
                return acc_detail