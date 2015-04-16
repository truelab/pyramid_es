from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from unittest import TestCase


class TestDefaultAdapter(TestCase):

    def test_bwc_adapter_iface(self):
        from ..interfaces import IElastic
        from ..elastic import ElasticBWC
        adapter = ElasticBWC(None)
        self.assertTrue(IElastic.providedBy(adapter))

    def test_verify_adapter(self):
        from ..interfaces import IElastic
        from ..elastic import ElasticBWC
        from zope.interface.verify import verifyObject
        adapter = ElasticBWC(None)
        self.assertTrue(verifyObject(IElastic, adapter))


class TestCustomAdapter(TestCase):

    def setUp(self):
        from ..client import ElasticClient
        from ..mixin import ElasticMixin, ESMapping, ESString
        from sqlalchemy import Column, types
        from sqlalchemy.ext.declarative import declarative_base
        from zope.interface import implements, Interface
        Base = declarative_base()

        class ITodo(Interface):
            pass
        self.ITodo = ITodo

        class Todo(Base, ElasticMixin):
            implements(ITodo)
            __tablename__ = 'todos'
            id = Column(types.Integer, primary_key=True)
            description = Column(types.Unicode(40))

            @classmethod
            def elastic_mapping(cls):
                return ESMapping(
                    analyzer='content',
                    properties=ESMapping(
                        ESString('description', boost=5.0)))
        self.Todo = Todo
        self.client = ElasticClient(servers=['localhost:9200'],
                                    index='pyramid_es_tests_txn',
                                    use_transaction=True)
        self.client.ensure_index(recreate=True)
        self.client.ensure_mapping(Todo)

    def test_index_and_delete_document(self):
        """ We are testing the default indexing strategy.
            Since the registry is not initialized, it will be looked up
            the ElasticBWC adapter by default as fallback
        """
        import transaction
        todo = self.Todo(id=42, description='Finish exhaustive test suite')

        with transaction.manager:
            self.client.index_object(todo)
        self.client.flush(force=True)
        self.client.refresh()

        # Search for this document and make sure it exists.
        q = self.client.query(self.Todo, q='Yeah!')
        self.assertEquals(0, q.execute().total)

        # Search for this document and make sure it exists.
        q = self.client.query(self.Todo, q='exhaustive')
        result = q.execute()
        todos = [doc.description for doc in result]
        self.assertIn('Finish exhaustive test suite', todos)

        with transaction.manager:
            self.client.delete_object(todo)

        self.client.flush(force=True)
        self.client.refresh()

        # Search for this document and make sure it DOES NOT exist.
        q = self.client.query(self.Todo, q='exhaustive')
        result = q.execute()
        todos = [doc.description for doc in result]
        self.assertNotIn('Finish exhaustive test suite', todos)

    def test_index_and_delete_document_custom(self):
        """ We register a custom adapter that alters the indexing strategy """
        from ..elastic import ElasticBWC
        from ..interfaces import IElastic
        from pyramid.threadlocal import get_current_registry
        registry = get_current_registry()

        class CustomES(ElasticBWC):
            @property
            def description(self):
                return "Yeah! %s" % self.context.description
        registry.registerAdapter(CustomES, (self.ITodo,), provided=IElastic)
        import transaction
        todo = self.Todo(id=42, description='Finish exhaustive test suite')

        with transaction.manager:
            self.client.index_object(todo)
        self.client.flush(force=True)
        self.client.refresh()

        # Search for this document and make sure it exists.
        q = self.client.query(self.Todo, q='exhaustive')
        result = q.execute()
        todos = [doc.description for doc in result]
        self.assertIn('Yeah! Finish exhaustive test suite', todos)

        # Search for this document and make sure it exists.
        q = self.client.query(self.Todo, q='Yeah!')
        result = q.execute()
        self.assertEquals(1, result.total)

        with transaction.manager:
            self.client.delete_object(todo)

        self.client.flush(force=True)
        self.client.refresh()

        # Search for this document and make sure it DOES NOT exist.
        q = self.client.query(self.Todo, q='exhaustive')
        result = q.execute()
        todos = [doc.description for doc in result]
        self.assertNotIn('Yeah! Finish exhaustive test suite', todos)
