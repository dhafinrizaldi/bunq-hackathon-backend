# django-backend/split_app/settings.py

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'splitdb',
        'USER': 'splituser',
        'PASSWORD': 'splitpassword',
        'HOST': '127.0.0.1',
        'PORT': '5432',
    }
}