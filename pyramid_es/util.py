from pyramid.threadlocal import get_current_registry

from .interfaces import IElastic


def get_registry_from_resource(resource):
    request = getattr(resource, 'request', None)
    if request is not None:
        registry = getattr(request, 'registry', None)
        if registry is not None:
            return registry
    return get_current_registry()


def get_elastic_adapter(resource):
    registry = get_registry_from_resource(resource)
    elastic_adapter = registry.queryAdapter(resource, IElastic)
    return elastic_adapter
