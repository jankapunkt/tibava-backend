from django.http import JsonResponse
from django.contrib import auth
from django.views.decorators.http import require_http_methods

from django.views.decorators.csrf import ensure_csrf_cookie
import logging
import json
import traceback

from django.views.decorators.csrf import csrf_protect
from django.views import View

# def get_csrf_token(request):
#     token = get_token(request)
#     return JsonResponse({"token": token})


@ensure_csrf_cookie
def get_csrf_token(request):
    # token = get_token(request)
    return JsonResponse({"status": "ok"})


class UserGet(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"status": "error", "error": {"type": "not_authenticated"}})

        try:
            user = request.user
            return JsonResponse(
                {
                    "status": "ok",
                    "data": {
                        "username": user.get_username(),
                        "email": user.email,
                        "date": user.date_joined,
                    },
                }
            )
        except Exception as e:
            logging.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


@require_http_methods(["POST"])
def login(request):
    try:
        body = request.body.decode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        body = request.body

    try:
        data = json.loads(body)
    except Exception as e:
        print("Search: JSON error: {}".format(e), flush=True)
        return JsonResponse({"status": "error"})

    if "name" not in data["params"]:
        print("name", flush=True)
        return JsonResponse({"status": "error"})

    if "password" not in data["params"]:
        print("password", flush=True)
        return JsonResponse({"status": "error"})

    username = data["params"]["name"]
    password = data["params"]["password"]

    if username == "" or password == "":
        return JsonResponse({"status": "error"})

    user = auth.authenticate(username=username, password=password)
    if user is not None:
        auth.login(request, user)
        return JsonResponse(
            {
                "status": "ok",
                "data": {
                    "username": user.get_username(),
                    "email": user.email,
                    "date": user.date_joined,
                },
            }
        )

    return JsonResponse({"status": "error"})


@require_http_methods(["POST"])
def register(request):
    try:
        body = request.body.decode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        body = request.body

    try:
        data = json.loads(body)
    except Exception as e:
        print("Search: JSON error: {}".format(e), flush=True)
        return JsonResponse({"status": "error"})

    print(data, flush=True)
    if "name" not in data["params"]:
        print("name", flush=True)
        return JsonResponse({"status": "error"})

    if "password" not in data["params"]:
        print("password", flush=True)
        return JsonResponse({"status": "error"})

    if "email" not in data["params"]:
        print("email", flush=True)
        return JsonResponse({"status": "error"})

    username = data["params"]["name"]
    password = data["params"]["password"]
    email = data["params"]["email"]

    if username == "" or password == "" or email == "":
        print("An input is missing.", flush=True)
        return JsonResponse({"status": "error"})

    if auth.get_user_model().objects.filter(username=username).count() > 0:
        print("User already exists. Abort.", flush=True)
        return JsonResponse({"status": "error"})

    # TODO Add EMail register here
    user = auth.get_user_model().objects.create_user(username, email, password)
    user = auth.authenticate(username=username, password=password)

    if user is not None:
        auth.login(request, user)
        return JsonResponse({"status": "ok"})

    return JsonResponse({"status": "error"})


@require_http_methods(["POST"])
def logout(request):
    auth.logout(request)
    return JsonResponse({"status": "ok"})
