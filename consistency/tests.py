# SYSTEM
from __future__ import absolute_import

# LIBRARIES
from djangae.test import inconsistent_db
from django.db import models
from django.test import TestCase

# CONSISTENCY
from consistency.consistency import improve_queryset_consistency


class TestModel(models.Model):
    name = models.CharField(max_length=100)


class ConsistencyTests(TestCase):

    def test_basic_functionality(self):
        existing = TestModel.objects.create(name='existing')
        queryset = TestModel.objects.all()
        self.assertItemsEqual(queryset.all(), [existing])
        # Add a new object with eventual consistency being slow
        with inconsistent_db():
            new = TestModel.objects.create(name='new')
            # The new object should not yet be returned
            self.assertItemsEqual(queryset.all(), [existing])
            # But using our handy function it should be returned
            consistent = improve_queryset_consistency(queryset)
            self.assertItemsEqual(consistent.all(), [existing, new])
