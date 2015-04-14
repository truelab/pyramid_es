from zope.interface import (
    Interface,
    Attribute,
    )


class IElastic(Interface):
    """
    IElastic adapter.
    """

    __elastic_parent__ = Attribute("The elastic parent")  # TODO: necessary?
    elastic_parent = Attribute("The elastic parent")      # TODO: necessary?

    def elastic_mapping():
        """
        Return an ES mapping.
        """

    def elastic_document_type():
        """
        The elastic document type
        """

    def elastic_document():
        """
        Apply the class ES mapping to the current context
        """

    def elastic_document_id():
        """
        Returns the document id
        """
