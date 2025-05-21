from django.shortcuts import render, redirect
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponse
import json
from django.conf import settings
from django.db.models import Q
from django.db.models import F
from django.core.paginator import Paginator
from django.views import View



# 判断用户是否登陆
def checkLogin(func):
    def wrapper(request, *args, **kwargs):
        if request.user.is_anonymous:
            # if not request.user.authenticated():
            next = request.get_full_path()
            if request.method=="POST":
                ###当前页面
                return nologinResponseCommon({"url":reverse("login")+'?next=' + next},"需要登录")
            return redirect(reverse("login")+'?next=' + next)
        else:
            return func(request, *args, **kwargs)

    return wrapper


def successResponseCommon(data, message="success"):
    return HttpResponse(json.dumps({"code": 200, "data": data, "message": message}, ensure_ascii=False),
                        content_type="application/json")


def errorResponseCommon(data, message):
    return HttpResponse(json.dumps({"code": 500, "data": data, "message": message}, ensure_ascii=False),
                        content_type="application/json")


def failedResponseCommon(code, data, message="failed"):
    return HttpResponse(json.dumps({"code": code, "data": data, "message": message}, ensure_ascii=False),
                        content_type="application/json")
def nologinResponseCommon(data, message):
    return HttpResponse(json.dumps({"code": 401, "data": data, "message": message}, ensure_ascii=False), content_type="application/json")


def timeConverStr(timepar):
    # timepar=datetime.strptime(timepar, '%Y-%m-%d %H:%M:%S') #字符串转时间
    return timepar.strftime('%Y-%m-%d %H:%M:%S')


def EmailCheck(email):
    import re
    regex = re.compile(r'([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+')
    if re.fullmatch(regex, email):
        return True
    else:
        return False

