import pytest

import pymsgraph


@pytest.fixture
def client():
    return pymsgraph.Client("test", "test", "str", _test=True)


@pytest.fixture
def url():
    return "https://graph.microsoft.com/v1.0"


@pytest.fixture
def request_query_param():
    return {
        "SELECT": False,
        "EXPAND": False,
        "FILTER": False,
        "ORDERBY": False,
        "TOP": False,
        "COUNT": False,
        "SEARCH": False,
    }


@pytest.fixture
def request_method():
    return {
        "GET": False,
        "POST": False,
        "PATCH": False,
        "DELETE": False,
    }


@pytest.fixture
def check_request_attributes(request_method, request_query_param):
    def check_request_query_param(obj, **kwargs):
        for k, v in kwargs.items():
            request_query_param[k] = v

        for k, v in request_query_param.items():
            assert v == getattr(obj.RequestQueryParam, k)

    def check_request_method(obj, **kwargs):
        for k, v in kwargs.items():
            request_method[k] = v

        for k, v in request_method.items():
            assert v == getattr(obj.RequestMethod, k)

    def wrapper(obj, _type, **kwargs):
        func = func_mapping[_type]
        func(obj, **kwargs)

    func_mapping = {
        "method": check_request_method,
        "query_param": check_request_query_param,
    }
    return wrapper
