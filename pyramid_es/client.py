from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import logging

from itertools import chain
from pprint import pformat
from functools import wraps

import six

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

import transaction as zope_transaction
from zope.interface import implementer
from transaction.interfaces import ISavepointDataManager

from .query import ElasticQuery
from .result import ElasticResultRecord
from .util import get_elastic_adapter

log = logging.getLogger(__name__)


ANALYZER_SETTINGS = {
    "analysis": {
        "filter": {
            "snowball": {
                "type": "snowball",
                "language": "English"
            },
        },

        "analyzer": {
            "lowercase": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["standard", "lowercase"]
            },

            "email": {
                "type": "custom",
                "tokenizer": "uax_url_email",
                "filter": ["standard", "lowercase"]
            },

            "content": {
                "type": "custom",
                "tokenizer": "standard",
                "char_filter": ["html_strip"],
                "filter": ["standard", "lowercase", "stop", "snowball"]
            }
        }
    }
}


CREATE_INDEX_SETTINGS = ANALYZER_SETTINGS.copy()
CREATE_INDEX_SETTINGS.update({
    "index": {
        "number_of_shards": 2,
        "number_of_replicas": 0
    },
})

STATUS_ACTIVE = 'active'
STATUS_CHANGED = 'changed'


_CLIENT_STATE = {}


@implementer(ISavepointDataManager)
class ElasticDataManager(object):
    def __init__(self, client, transaction_manager):
        self.client = client
        self.transaction_manager = transaction_manager
        t = transaction_manager.get()
        t.join(self)
        _CLIENT_STATE[id(client)] = STATUS_ACTIVE

        self._reset()

    def _reset(self):
        log.error('_reset(%s)', self)
        self.client.uncommitted = []

    def _finish(self):
        log.error('_finish(%s)', self)
        client = self.client
        del _CLIENT_STATE[id(client)]

    def abort(self, transaction):
        log.error('abort(%s)', self)
        self._reset()
        self._finish()

    def tpc_begin(self, transaction):
        log.error('tpc_begin(%s)', self)
        pass

    def commit(self, transaction):
        log.error('commit(%s)', self)
        pass

    def tpc_vote(self, transaction):
        log.error('tpc_vote(%s)', self)
        # XXX Ideally, we'd try to check the uncommitted queue and make sure
        # everything looked ok. Note sure how we can do that, though.
        pass

    def tpc_finish(self, transaction):
        # Actually persist the uncommitted queue.
        log.error('tpc_finish(%s)', self)
        log.warn("running: %r", self.client.uncommitted)
        for cmd, args, kwargs in self.client.uncommitted:
            kwargs['immediate'] = True
            getattr(self.client, cmd)(*args, **kwargs)
        self._reset()
        self._finish()

    def tpc_abort(self, transaction):
        log.error('tpc_abort()')
        self._reset()
        self._finish()

    def sortKey(self):
        # NOTE: Ideally, we want this to sort *after* database-oriented data
        # managers, like the SQLAlchemy one. The double tilde should get us
        # to the end.
        return '~~elasticsearch' + str(id(self))

    def savepoint(self):
        return ElasticSavepoint(self)


class ElasticSavepoint(object):

    def __init__(self, dm):
        self.dm = dm
        self.saved = dm.client.uncommitted.copy()

    def rollback(self):
        self.dm.client.uncommitted = self.saved.copy()


def join_transaction(client, transaction_manager):
    client_id = id(client)
    existing_state = _CLIENT_STATE.get(client_id, None)
    if existing_state is None:
        log.error('client %s not found, setting up new data manager',
                  client_id)
        ElasticDataManager(client, transaction_manager)
    else:
        log.error('client %s found, using existing data manager',
                  client_id)
        _CLIENT_STATE[client_id] = STATUS_CHANGED


def transactional(f):
    @wraps(f)
    def transactional_inner(client, *args, **kwargs):
        immediate = kwargs.pop('immediate', None)
        if client.use_transaction:
            if immediate:
                return f(client, *args, **kwargs)
            else:
                log.error('enqueueing action: %s: %r, %r', f.__name__, args,
                          kwargs)
                join_transaction(client, client.transaction_manager)
                client.uncommitted.append((f.__name__, args, kwargs))
                return
        return f(client, *args, **kwargs)
    return transactional_inner


class ElasticClient(object):
    """
    A handle for interacting with the Elasticsearch backend.
    """

    def __init__(self, servers, index, timeout=1.0, disable_indexing=False,
                 use_transaction=True,
                 transaction_manager=zope_transaction.manager):
        self.index = index
        self.disable_indexing = disable_indexing
        self.use_transaction = use_transaction
        self.transaction_manager = transaction_manager
        self.es = Elasticsearch(servers)

    def ensure_index(self, recreate=False):
        """
        Ensure that the index exists on the ES server, and has up-to-date
        settings.
        """
        exists = self.es.indices.exists(self.index)
        if recreate or not exists:
            if exists:
                self.es.indices.delete(self.index)
            self.es.indices.create(self.index,
                                   body=dict(settings=CREATE_INDEX_SETTINGS))

    def delete_index(self):
        """
        Delete the index on the ES server.
        """
        self.es.indices.delete(self.index)

    def ensure_mapping(self, cls, recreate=False):
        """
        Put an explicit mapping for the given class if it doesn't already
        exist.
        """
        doc_type = cls.__name__
        doc_mapping = cls.elastic_mapping()

        doc_mapping = dict(doc_mapping)
        if cls.elastic_parent:
            doc_mapping["_parent"] = {
                "type": cls.elastic_parent
            }

        doc_mapping = {doc_type: doc_mapping}

        log.debug('Putting mapping: \n%s', pformat(doc_mapping))
        if recreate:
            try:
                self.es.indices.delete_mapping(index=self.index,
                                               doc_type=doc_type)
            except NotFoundError:
                pass
        self.es.indices.put_mapping(index=self.index,
                                    doc_type=doc_type,
                                    body=doc_mapping)

    def delete_mapping(self, cls):
        """
        Delete the mapping corresponding to ``cls`` on the server. Does not
        delete subclass mappings.
        """
        doc_type = cls.__name__
        self.es.indices.delete_mapping(index=self.index,
                                       doc_type=doc_type)

    def ensure_all_mappings(self, base_class, recreate=False):
        """
        Initialize explicit mappings for all subclasses of the specified
        SQLAlcehmy declarative base class.
        """
        for cls in base_class._decl_class_registry.values():
            if hasattr(cls, 'elastic_mapping'):
                self.ensure_mapping(cls, recreate=recreate)

    def get_mappings(self, cls=None):
        """
        Return the object mappings currently used by ES.
        """
        doc_type = cls and cls.__name__
        raw = self.es.indices.get_mapping(index=self.index,
                                          doc_type=doc_type)
        return raw[self.index]['mappings']

    def index_object(self, obj, **kw):
        """
        Add or update the indexed document for an object.
        """
        elastic_adapter = get_elastic_adapter(obj)
        doc = elastic_adapter.elastic_document()

        doc_type = elastic_adapter.elastic_document_type()
        doc_id = doc.pop("_id")
        doc_parent = elastic_adapter.elastic_parent

        log.debug('Indexing object:\n%s', pformat(doc))
        log.debug('Type is %r', doc_type)
        log.debug('ID is %r', doc_id)
        log.debug('Parent is %r', doc_parent)

        self.index_document(id=doc_id,
                            doc_type=doc_type,
                            doc=doc,
                            parent=doc_parent,
                            **kw)

    def delete_object(self, obj, safe=False, **kw):
        """
        Delete the indexed document for an object.
        """
        elastic_adapter = get_elastic_adapter(obj)
        doc = elastic_adapter.elastic_document()

        doc_type = elastic_adapter.elastic_document_type()
        doc_id = doc.pop("_id")
        doc_parent = elastic_adapter.elastic_parent

        self.delete_document(id=doc_id,
                             doc_type=doc_type,
                             parent=doc_parent,
                             safe=safe,
                             **kw)

    @transactional
    def index_document(self, id, doc_type, doc, parent=None):
        """
        Add or update the indexed document from a raw document source (not an
        object).
        """
        if self.disable_indexing:
            return

        kwargs = dict(index=self.index,
                      body=doc,
                      doc_type=doc_type,
                      id=id)
        if parent:
            kwargs['parent'] = parent
        self.es.index(**kwargs)

    @transactional
    def delete_document(self, id, doc_type, parent=None, safe=False):
        """
        Delete the indexed document based on a raw document source (not an
        object).
        """
        if self.disable_indexing:
            return

        kwargs = dict(index=self.index,
                      doc_type=doc_type,
                      id=id)
        if parent:
            kwargs['routing'] = parent
        try:
            self.es.delete(**kwargs)
        except NotFoundError:
            if not safe:
                raise

    def index_objects(self, objects):
        """
        Add multiple objects to the index.
        """
        for obj in objects:
            self.index_object(obj)

    def flush(self, force=True):
        self.es.indices.flush(force=force)

    def get(self, obj, routing=None):
        """
        Retrieve the ES source document for a given object or (document type,
        id) pair.
        """
        if isinstance(obj, tuple):
            doc_type, doc_id = obj
        else:
            elastic_adapter = get_elastic_adapter(obj)
            doc_type = elastic_adapter.elastic_document_type()
            doc_id = elastic_adapter.elastic_document_id()
            elastic_parent = elastic_adapter.elastic_parent
            if elastic_parent:
                routing = elastic_parent

        kwargs = dict(index=self.index,
                      doc_type=doc_type,
                      id=doc_id)
        if routing:
            kwargs['routing'] = routing
        r = self.es.get(**kwargs)
        return ElasticResultRecord(r)

    def refresh(self):
        """
        Refresh the ES index.
        """
        self.es.indices.refresh(index=self.index)

    def subtype_names(self, cls):
        """
        Return a list of document types to query given an object class.
        """
        classes = [cls] + [m.class_ for m in
                           cls.__mapper__._inheriting_mappers]
        return [c.__name__ for c in classes
                if hasattr(c, "elastic_mapping")]

    def search(self, body, classes=None, fields=None, **query_params):
        """
        Run ES search using default indexes.
        """
        doc_types = classes and list(chain.from_iterable(
            [doc_type] if isinstance(doc_type, six.string_types) else
            self.subtype_names(doc_type)
            for doc_type in classes))

        if fields:
            query_params['fields'] = fields

        return self.es.search(index=self.index,
                              doc_type=','.join(doc_types),
                              body=body,
                              **query_params)

    def query(self, *classes, **kw):
        """
        Return an ElasticQuery against the specified class.
        """
        cls = kw.pop('cls', ElasticQuery)
        return cls(client=self, classes=classes, **kw)
