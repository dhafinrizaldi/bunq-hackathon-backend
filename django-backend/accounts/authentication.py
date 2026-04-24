from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
class CookieJWTAuthentication(JWTAuthentication):

    def authenticate(self, request):
        # Get the token from cookies
        print('############### AUTHENTICATING ##############')
        access_token = request.COOKIES.get('access_token')
        print('access token: ', access_token)
        try:
            # Validate the token
            validated_token = self.get_validated_token(access_token)
        except AuthenticationFailed as e:
            raise AuthenticationFailed(f'Token validation failed: {str(e)}')

        try:
            # Retrieve the user
            user = self.get_user(validated_token)
            return user, validated_token
        except AuthenticationFailed as e:

            raise AuthenticationFailed(f'Error retrieving user: {str(e)}')
