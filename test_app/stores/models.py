import uuid
from django.utils import timezone
from django.db import models
from djmoney.models.fields import MoneyField
from collections import OrderedDict
#import stores.middleware
#from stores.middleware import *
import django_multitenant
from django_multitenant import *
import pdb


def autoTimestamp():
    # TODO: force a real database column default like "NOW"
    return models.DateTimeField(editable=False, default=timezone.now)

class Store(models.Model):
    """
    Defines a model with a `name` field and a `tenant_id` field, which is set to
    the value `'id'`.

    Attributes:
        name (CharFieldmax_length255): A non-nullable field that stores a string
            value.
        tenant_id (str|int): Assigned the value `'id'`.

    """
    name = models.CharField(max_length=255)
    tenant_id='id'

class Product(TenantModel):
    """
    Models a product within a store, linking it to its store of origin via a foreign
    key. It also provides a convenient way to access the associated store through
    the `get_tenant()` method.

    Attributes:
        store (ForeignKeyStore): A reference to a Store object, which establishes
            a relationship between Products and Stores.
        tenant_id (str|int): A ForeignKey referencing the `Store` model, establishing
            a unique identifier for each product within a particular store.
        name (CharFieldmax_length255): Used to store a short name for the product.
        description (TextField): Maximum length of 255 characters, allowing for a
            brief text description of the product.

    """
    store = models.ForeignKey(Store)
    tenant_id='store_id'

    def get_tenant():
        return self.store

    name = models.CharField(max_length=255)
    description = models.TextField()
    class Meta(object):
        unique_together = ["id", "store"]

class Purchase(TenantModel):
    """
    Models a purchase made by a tenant, linking the purchase to a store and a
    product, with an optional quantity.

    Attributes:
        store (ForeignKeyStore): A reference to the store associated with the purchase.
        tenant_id (str|int): A ForeignKey to the `Store` model, which establishes
            a unique identifier for each purchase made by a specific tenant.
        product (ForeignKeyProduct): Linked to a product object in the Product
            model using a foreign key relationship.
        quantity (IntegerField): Defaulted to zero. It represents the quantity of
            a product purchased by a tenant from a store.

    """
    store = models.ForeignKey(Store)
    tenant_id='store_id'
    product = models.ForeignKey(Product,
        db_constraint=False,
        db_index=False,
    )
    quantity = models.IntegerField(default=0)
    class Meta(object):
        unique_together = ["id", "store"]

# TODO: add a Customer model
