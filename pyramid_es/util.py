from pyramid.threadlocal import get_current_registry

from .interfaces import IElastic
from .elastic import ElasticBWC


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
    if elastic_adapter is None:
        # If no IElastic adapter is found, we assume you are
        # working with the traditional method based on mixin
        # class. We just return the fallback default adapter.
        # We don't use the default keyword argument of
        # the queryAdapter method, less overhead
        elastic_adapter = ElasticBWC(resource)
    return elastic_adapter
