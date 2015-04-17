from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from unittest import TestCase


class TestDefaultAdapter(TestCase):

    def test_client_no_pyramid_es_client(self):
        from pyramid.testing import DummyRequest
        fake_request = DummyRequest()

        self.assertFalse(hasattr(fake_request, 'pyramid_es_client'))
        self.assertTrue(hasattr(fake_request, 'registry'))
        self.assertFalse(hasattr(fake_request.registry, 'pyramid_es_client'))

        from pyramid_es import get_client
        import mock
        with mock.patch('pyramid_es.get_current_registry') as current_reg:
            current_reg.return_value = mock.Mock(pyramid_es_client=1)
            fake_client = get_client(fake_request)
        self.assertEquals(1, fake_client)

    def test_client_no_pyramid_es_client_no_registry(self):
        class FakeRequest:
            pass
        fake_request = FakeRequest()

        self.assertFalse(hasattr(fake_request, 'pyramid_es_client'))
        self.assertFalse(hasattr(fake_request, 'registry'))

        from pyramid_es import get_client
        import mock
        with mock.patch('pyramid_es.get_current_registry') as current_reg:
            current_reg.return_value = mock.Mock(pyramid_es_client=1)
            fake_client = get_client(fake_request)
        self.assertEquals(1, fake_client)
