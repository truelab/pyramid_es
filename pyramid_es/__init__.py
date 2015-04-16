from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from pyramid.settings import asbool
from pyramid.threadlocal import get_current_registry

from .client import ElasticClient
from .elastic import ElasticBWC
from .interfaces import IElastic


__version__ = '0.3.2.dev'


def client_from_config(settings, prefix='elastic.'):
    """
    Instantiate and configure an Elasticsearch from settings.

    In typical Pyramid usage, you shouldn't use this directly: instead, just
    include ``pyramid_es`` and use the :py:func:`get_client` function to get
    access to the shared :py:class:`.client.ElasticClient` instance.
    """
    return ElasticClient(
        servers=settings.get(prefix + 'servers', ['localhost:9200']),
        timeout=settings.get(prefix + 'timeout', 1.0),
        index=settings[prefix + 'index'],
        use_transaction=asbool(settings.get(prefix + 'use_transaction', True)),
        disable_indexing=settings.get(prefix + 'disable_indexing', False))


def includeme(config):
    registry = config.registry
    settings = registry.settings

    client = client_from_config(settings)
    if asbool(settings.get('elastic.ensure_index_on_start')):
        client.ensure_index()

    # register BWC adapter
    config.registry.registerAdapter(ElasticBWC, provided=IElastic)

    registry.pyramid_es_client = client


def get_client(request):
    """
    Get the registered Elasticsearch client. The supplied argument can be
    either a ``Request`` instance or a ``Registry``.
    """
    registry = getattr(request, 'registry', None)
    if registry is None:
        registry = request
    if not hasattr(registry, 'pyramid_es_client'):
        registry = get_current_registry()
    return registry.pyramid_es_client
