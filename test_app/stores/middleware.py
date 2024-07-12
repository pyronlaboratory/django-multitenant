from django.apps import apps
from django.db import models
try:
    from threading import local
except ImportError:
    from django.utils._threading_local import local

from djmoney.models.fields import MoneyField
from collections import OrderedDict
import pdb

_thread_locals = local()


#Modified QuerySet to add suitable filters on joins.
class TenantQuerySet(models.QuerySet):
    
    #This is adding tenant filters for all the models in the join.
    """
    Adds tenant-specific filters to a query set using aliases and joins. It also
    provides extra parameters for filtering, sorting, and aggregating results based
    on tenant information.

    """
    def add_tenant_filters_with_joins(self):
        """
        Filters model instances based on tenant IDs by appending join conditions
        to the query set's extra parameters.

        """
        current_tenant=get_current_tenant()
        if current_tenant:
            l=[]
            current_table_name=self.model._meta.db_table
            alias_refcount = self.query.alias_refcount
            alias_map = self.query.alias_map
            for k,v in alias_refcount.items():
                if(v>0 and k!=current_table_name):
                    current_model=get_model_by_db_table(alias_map[k].table_name)
                    l.append(k+'.'+current_model.tenant_id+'='+str(current_tenant.id))
            self.query.add_extra([],[],l,[],[],[])

    # def add_tenant_filters(self):
    #     self.add_tenant_filters_without_joins()
    #     self.add_tenant_filters_with_joins()
    
    def add_tenant_filters_without_joins(self):
        """
        Filters queries based on the current tenant ID, adding related table field
        filters to the queryset without using joins.

        """
        current_tenant=get_current_tenant()
        if current_tenant:
            l=[]
            table_name=self.model._meta.db_table
            l.append(table_name+'.'+self.model.tenant_id+'='+str(current_tenant.id))
            self.query.add_extra([],[],l,[],[],[])

    #Below are APIs which generate SQL, this is where the tenant_id filters are injected for joins.
    
    def __iter__(self):
        """
        Adds tenant filters with joins before iterating over the superclass's
        implementation, allowing for more efficient and targeted querying of tenant
        data.

        Returns:
            object: An instance of `TenantQuerySet`.

        """
        self.add_tenant_filters_with_joins()
        return super(TenantQuerySet,self).__iter__()
    
    def aggregate(self, *args, **kwargs):
        """
        Adds tenant filters with joins and then calls the superclass's `aggregate`
        method to perform further aggregation.

        Args:
            *args (list): List of positional arguments
            **kwargs (dict): Dictionary of keyword arguments

        Returns:
            object: A result of applying aggregation to a queryset of tenants using
            joins and other operations.

        """
        self.add_tenant_filters_with_joins()
        return super(TenantQuerySet,self).aggregate(*args, **kwargs)

    def count(self):
        """
        Adds tenant filters with joins and then calls the superclass's `count`
        method to retrieve the count of tenants.

        Returns:
            int: The number of tenants that match the filters applied by the
            `add_tenant_filters_with_joins` method.

        """
        self.add_tenant_filters_with_joins()
        return super(TenantQuerySet,self).count()

    def get(self, *args, **kwargs):
        #self.add_tenant_filters()
        """
        Adds tenant filters with joins and then queries the data using the
        superclass's implementation, returning the result.

        Args:
            *args (list): List of positional arguments
            **kwargs (dict): Dictionary of keyword arguments

        Returns:
            Tenant|None: A subclass of QuerySet and represents a single tenant or
            None if no matching tenants are found.

        """
        self.add_tenant_filters_with_joins()
        return super(TenantQuerySet,self).get(*args,**kwargs)

    # def get_or_create(self, defaults=None, **kwargs):
    #     self.add_tenant_filters()
    #     return super(TenantQuerySet,self).get_or_create(defaults,**kwargs)

    # def update(self, **kwargs):
    #     self.add_tenant_filters_without_joins()
    #     #print(self.query.alias_refcount)
    #     return super(TenantQuerySet,self).update(**kwargs)
    
    # def _update(self, values):
    #     self.add_tenant_filters_without_joins()
    #     #print(self.query.alias_refcount)
    #     return super(TenantQuerySet,self)._update(values)
    
    #This API is called when there is a subquery. Injected tenant_ids for the subqueries.
    def _as_sql(self, connection):
        """
        Adds tenant filters with joins and then calls the superclass's `_as_sql`
        method to generate the SQL query for the filtered results.

        """
        self.add_tenant_filters_with_joins()
        return super(TenantQuerySet,self)._as_sql(connection)

#Below is the manager related to the above class. 
class TenantManager(TenantQuerySet.as_manager().__class__):
    #Injecting tenant_id filters in the get_queryset.
    #Injects tenant_id filter on the current model for all the non-join/join queries. 
    """
    Filters and queries tenants based on their ID, using the current tenant's ID
    to tailor the queryset.

    """
    def get_queryset(self):
        """
        Filters the queryset of objects based on the current tenant ID, using the
        `get_current_tenant()` function to retrieve the current tenant and passing
        the filtered queryset to the superclass's `get_queryset()` method.

        Returns:
            Dict[str,int]: A filterd queryset of objects of type TenantManager's
            model based on the current tenant ID.

        """
        current_tenant=get_current_tenant()
        if current_tenant:
            kwargs = { self.model.tenant_id: current_tenant.id}
            return super(TenantManager, self).get_queryset().filter(**kwargs)
        return super(TenantManager, self).get_queryset()

#Abstract model which all the models related to tenant inherit.
class TenantModel(models.Model):

    #New manager from middleware
    """
    Provides an abstraction layer for updating tenant-related data in a database,
    allowing child classes to specify which fields to update and how to filter
    related records based on the current tenant.

    Attributes:
        objects (TenantManager|None): Used to manage instances of the model.
        tenant_id (str|int): Used to identify the current tenant for which the
            model instance is responsible, as set by the `objects` attribute.

    """
    objects = TenantManager()
    tenant_id=''

    #adding tenant filters for save
    #Citus requires tenant_id filters for update, hence doing this below change.
    def _do_update(self, base_qs, using, pk_val, values, update_fields, forced_update):
        """
        Updates an instance of the model based on input parameters, filtering the
        base query set by the current tenant's ID and applying superclass updates.

        """
        current_tenant=get_current_tenant()
        if current_tenant:
            kwargs = { self.tenant_id: current_tenant.id}
            base_qs = base_qs.filter(**kwargs)
        return super(TenantModel,self)._do_update(base_qs, using, pk_val, values, update_fields, forced_update)

    class Meta:
        abstract = True

def get_current_user():
    """
    Despite arguments to the contrary, it is sometimes necessary to find out who is the current
    logged in user, even if the request object is not in scope.  The best way to do this is 
    by storing the user object in middleware while processing the request.
    """
    return getattr(_thread_locals, 'user', None)

def get_model_by_db_table(db_table):
    """
    Searches through a Django app's models for the one with the matching db_table
    name, returning it if found. If not found, it raises a `ValueError`.

    Args:
        db_table (str|int): Used to identify the name of the database table
            associated with a Django model.

    Returns:
        Model: A Python object representing a Django model instance associated
        with the specified database table name.

    """
    for model in apps.get_models():
        if model._meta.db_table == db_table:
            return model
    else:
        # here you can do fallback logic if no model with db_table found
        raise ValueError('No model found with db_table {}!'.format(db_table))
        # or return None

def get_current_tenant():
    """
    Retrieves the current tenant ID from the local thread storage and returns it.
    If no tenant is found, it sets the default tenant ID and retrieves it again.

    Returns:
        object: Ether `tenant` or `None`.

    """
    tenant = getattr(_thread_locals, 'tenant', None)

    # tenant may not be set yet, if request user is anonymous, or has no profile,
    # if not tenant:
    #     set_tenant_to_default()
    
    return getattr(_thread_locals, 'tenant', None)


# def set_tenant_to_default():
#     """
#     Sets the current tenant as per BASE_TENANT_ID.
#     """
#     # import is done from within the function, to avoid trouble 
#     from models import Tenant, BASE_TENANT_ID
#     set_current_tenant( Tenant.objects.get(id=BASE_TENANT_ID) )
    

def set_current_tenant(tenant):
    setattr(_thread_locals, 'tenant', tenant)


class ThreadLocals(object):
    """
    Maintains thread-local variables for user and tenant information. It sets these
    variables based on the `request` parameter, and raises an error if a User is
    created without a Profile.

    """
    def process_request(self, request):
        """
        Sets the `user` thread local variable to the user attribute of the incoming
        request, then checks if the user has a profile and sets the `tenant` thread
        local variable accordingly. If an exception occurs during this process, a
        ValueError is raised with a security-related message.

        Args:
            request (Any|Request): Provided as an instance of a Python class
                representing a web request.

        """
        _thread_locals.user = getattr(request, 'user', None)

        # Attempt to set tenant
        if _thread_locals.user and not _thread_locals.user.is_anonymous():
            try:
                profile = _thread_locals.user.get_profile()
                if profile:
                    _thread_locals.tenant = getattr(profile, 'tenant', None)
            except:
                raise ValueError(
                    """A User was created with no profile.  For security reasons, 
                    we cannot allow the request to be processed any further.
                    Try deleting this User and creating it again to ensure a 
                    UserProfile gets attached, or link a UserProfile 
                    to this User.""")
