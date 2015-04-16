from zope.interface import (
    implements,
    Interface,
    )
from zope.component import adapts
from .mixin import (
    ElasticParent,
    )
from .interfaces import IElastic


class ElasticBase(object):
    """ This is the base class you can extend in order to add ES
        capabilities to your objects.
    """

    def __init__(self, context):
        self.context = context

    def elastic_mapping(self):
        """
        Return an ES mapping.
        """
        raise NotImplementedError("You define a mapping")

    def elastic_document_type(self):
        """
        The elastic document type
        """
        raise NotImplementedError("You must define a document type")

    def elastic_document(self):
        """
        Apply the class ES mapping to the current context
        """
        return self.elastic_mapping()(self)

    def elastic_document_id(self):
        """
        Returns the document id
        """
        raise NotImplementedError("You must define a document id")

    __elastic_parent__ = None
    elastic_parent = ElasticParent()


class ElasticBWC(ElasticBase):
    """ Backwards compatible adapter for traditional ES mixin classes """
    implements(IElastic)
    adapts(Interface)

    def elastic_mapping(self):
        """
        Return an ES mapping.
        """
        return self.context.elastic_mapping()

    def elastic_document_type(self):
        """
        The elastic document type
        """
        return self.context.__class__.__name__

    def elastic_document_id(self):
        """
        Returns the document id
        """
        return self.context.id

    @property
    def elastic_parent(self):
        """ Overrides for backwards compatibility """
        return self.context.elastic_parent

    @property
    def __elastic_parent__(self):
        """ Overrides for backwards compatibility """
        return self.context.__elastic_parent__

    def __getattr__(self, key):
        """ This __getattr__ is not needed, we include it for backwards
            compatibility issues. This way existing resources that
            inherits from the ES mixin class will work without having
            to change the elastic mapping with an attr='context'.
        """
        if key not in ('elastic_mapping',
                       'elastic_document_type',
                       'elastic_document_id'):
            return getattr(self.context, key)
        return super(ElasticBWC, self).__get__(key)
