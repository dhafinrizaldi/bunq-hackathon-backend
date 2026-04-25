from rest_framework import serializers
from .models import CustomUser, Contact, SalarySetup, AllocationRule
from django.contrib.auth import authenticate
from rest_framework.exceptions import ValidationError

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = CustomUser
        fields = ('email', 'password')

    def create(self, validated_data):
        return CustomUser.objects.create_user(**validated_data)


class InactiveUserError(ValidationError):
    def __init__(self):
        super().__init__({
            'error': 'User account is inactive',
            'code': 'user_inactive'
        })

class InvalidCredentialsError(ValidationError):
    def __init__(self):
        super().__init__({
            'error': 'Invalid email or password',
            'code': 'invalid_credentials'
        })

class LoginUserSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=150, required=True)
    password = serializers.CharField(max_length=150, write_only=True)

    def validate(self, data):
        user = authenticate(email=data['email'], password=data['password'])

        if user is not None:
            if user.is_active:
                return user
            else:
                raise InactiveUserError()
        else:
            raise InvalidCredentialsError()


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["id", "nickname", "display_name", "iban", "bunq_user_id"]


class AllocationRuleSerializer(serializers.ModelSerializer):
    contact_nickname = serializers.SerializerMethodField()

    class Meta:
        model = AllocationRule
        fields = [
            "id", "rule_type", "amount_type", "amount",
            "contact_nickname", "invest_symbol", "savings_iban",
            "description", "order",
        ]

    def get_contact_nickname(self, obj):
        return obj.contact.nickname if obj.contact else None


class SalarySetupSerializer(serializers.ModelSerializer):
    rules = AllocationRuleSerializer(many=True, read_only=True)

    class Meta:
        model = SalarySetup
        fields = [
            "id", "raw_description", "trigger_keyword", "trigger_min_amount",
            "is_active", "rules", "created_at", "updated_at",
        ]