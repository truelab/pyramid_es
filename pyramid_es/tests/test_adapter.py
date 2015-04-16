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
