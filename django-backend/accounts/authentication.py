from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed


class CookieJWTAuthentication(JWTAuthentication):
    """JWT auth via the `access_token` cookie.

    Returns None when the cookie is absent so that other authentication classes
    (notably the default Bearer-header JWTAuthentication) get a chance.
    """

    def authenticate(self, request):
        access_token = request.COOKIES.get('access_token')
        if not access_token:
            return None
        try:
            validated_token = self.get_validated_token(access_token)
            user = self.get_user(validated_token)
            return user, validated_token
        except AuthenticationFailed:
            return None
