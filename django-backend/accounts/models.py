from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
import requests
from django.core.validators import MinValueValidator, MaxValueValidator

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
            
    def get_private_pem(self):
        return self.bunq_context['installation_context']['private_key_client']

class Contact(models.Model):
    """Address book entry — a real sandbox Bunq user the owner can send money to."""

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="contacts")
    nickname = models.CharField(max_length=64)
    display_name = models.CharField(max_length=255, blank=True)
    iban = models.CharField(max_length=34)
    bunq_user_id = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "nickname")

    def __str__(self):
        return f"{self.nickname} ({self.iban})"


class SalarySetup(models.Model):
    """
    Stores the trigger config and natural-language description of how a user
    wants their salary allocated when it arrives.
    """

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="salary_setup")
    raw_description = models.TextField(help_text="Original natural-language allocation instructions from the user.")
    trigger_keyword = models.CharField(max_length=128, help_text="Counterparty name to match (e.g. 'ASML').")
    trigger_min_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Minimum incoming amount (EUR) to trigger allocation.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} — trigger: {self.trigger_keyword} > €{self.trigger_min_amount}"


class AllocationRule(models.Model):
    """
    A single rule within a SalarySetup.
    Rules are executed in order when the salary trigger fires.
    """

    RULE_TYPE_TRANSFER = "transfer"
    RULE_TYPE_INVEST = "invest"
    RULE_TYPE_SAVE = "save"
    RULE_TYPES = [
        (RULE_TYPE_TRANSFER, "Transfer to contact"),
        (RULE_TYPE_INVEST, "Invest via Alpaca"),
        (RULE_TYPE_SAVE, "Move to savings account"),
    ]

    AMOUNT_TYPE_FIXED = "fixed"
    AMOUNT_TYPE_PERCENT = "percent"
    AMOUNT_TYPES = [
        (AMOUNT_TYPE_FIXED, "Fixed EUR amount"),
        (AMOUNT_TYPE_PERCENT, "Percentage of salary"),
    ]

    setup = models.ForeignKey(SalarySetup, on_delete=models.CASCADE, related_name="rules")
    rule_type = models.CharField(max_length=16, choices=RULE_TYPES)
    amount_type = models.CharField(max_length=8, choices=AMOUNT_TYPES)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Fixed EUR amount, or percentage (0–100) depending on amount_type.",
    )

    # Transfer-specific: resolved contact
    contact = models.ForeignKey(
        Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name="allocation_rules"
    )

    # Invest-specific: Alpaca ticker
    invest_symbol = models.CharField(max_length=16, blank=True, help_text="e.g. 'SPY', 'VOO'")

    # Save-specific: IBAN of savings monetary account
    savings_iban = models.CharField(max_length=34, blank=True)

    description = models.CharField(max_length=255, blank=True, help_text="Human-readable summary of this rule.")
    order = models.PositiveIntegerField(default=0, help_text="Execution order — lower runs first.")

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"[{self.order}] {self.rule_type} {self.amount_type}={self.amount} — {self.description}"
