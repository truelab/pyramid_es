from pyramid_es.mixin import (
    ElasticParent,
    )


class ElasticBase(object):
    """ This is the base class you can extend in order to add ES
        capabilities to your objects.
    """

    def __init__(self, context):
        self.context = context

    @classmethod
    def elastic_mapping(cls):
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
