import logging
from django.apps import apps
from django.db import models
try:
    from threading import local
except ImportError:
    from django.utils._threading_local import local

from collections import OrderedDict
import pdb

_thread_locals = local()
logger = logging.getLogger(__name__)


#Modified QuerySet to add suitable filters on joins.
class TenantQuerySet(models.QuerySet):
    
    #This is adding tenant filters for all the models in the join.
    """
    Adds tenant filters to a queryset based on the current tenant's ID, using joins
    or without joins depending on the method called. It also provides additional
    methods for iteration, aggregation, count, and getting an object.

    """
    def add_tenant_filters_with_joins(self):
        """
        Adds tenant-specific filters to the queryset by joining with other models
        and adding extra where clauses based on the current tenant.

        """
        current_tenant=get_current_tenant()
        if current_tenant:
            extra_sql=[]
            extra_params=[]
            current_table_name=self.model._meta.db_table
            alias_refcount = self.query.alias_refcount
            alias_map = self.query.alias_map
            for k,v in alias_refcount.items():
                if(v>0 and k!=current_table_name):
                    current_model=get_model_by_db_table(alias_map[k].table_name)
                    if issubclass(current_model, TenantModel):
                        extra_sql.append(k+'."'+current_model.tenant_id+'" = %s')
                        extra_params.append(current_tenant.id)
            self.query.add_extra([],[],extra_sql,extra_params,[],[])
    
    def add_tenant_filters_without_joins(self):
        """
        Adds tenant-specific filters to the queryset without using joins, by
        appending a list of filter fields and values to the queryset's extra parameters.

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
        Adds tenant filters with joins and then iterates over the resulting queryset
        using `super().__iter__()`.

        Returns:
            object: `TenantQuerySet`.

        """
        self.add_tenant_filters_with_joins()
        return super(TenantQuerySet,self).__iter__()
    
    def aggregate(self, *args, **kwargs):
        """
        Performs additional filtering and joining for each tenant, before calling
        the superclass's aggregate method to perform further aggregation.

        Args:
            *args (list): List of positional arguments
            **kwargs (dict): Dictionary of keyword arguments

        Returns:
            Any: The result of applying various aggregation operations to a
            TenantQuerySet instance.

        """
        self.add_tenant_filters_with_joins()
        return super(TenantQuerySet,self).aggregate(*args, **kwargs)

    def count(self):
        """
        Adds tenant filters with joins before calling the superclass's count method
        to retrieve the total number of tenants in the database.

        Returns:
            int: The count of the number of tenants that satisfy the filter
            conditions applied using the `add_tenant_filters_with_joins()` method
            and then the superclass `count()` method is called to provide the total
            count.

        """
        self.add_tenant_filters_with_joins()
        return super(TenantQuerySet,self).count()

    def get(self, *args, **kwargs):
        #self.add_tenant_filters()
        """
        Adds tenant filters and joins before returning the result of the superclass's
        `get` method.

        Args:
            *args (list): List of positional arguments
            **kwargs (dict): Dictionary of keyword arguments

        Returns:
            object: A subclass of `django.db.models.query.QuerySet`.

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
        Adds tenant filters with joins and then delegates the remaining SQL
        generation to the parent class's `_as_sql` method through super().

        """
        self.add_tenant_filters_with_joins()
        return super(TenantQuerySet,self)._as_sql(connection)

#Below is the manager related to the above class. 
class TenantManager(TenantQuerySet.as_manager().__class__):
    #Injecting tenant_id filters in the get_queryset.
    #Injects tenant_id filter on the current model for all the non-join/join queries. 
    """
    Filters tenant-related objects based on the current tenant's ID using the
    `get_queryset` method.

    """
    def get_queryset(self):
        """
        Filters tenants based on the current tenant's ID, using the `super()`
        method to first call the parent class's implementation and then apply
        custom filtering criteria using a dictionary of keyword arguments.

        Returns:
            Dict[str,int]: Used to filter a QuerySet of Tenant instances based on
            the current tenant ID.

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
    Provides an abstraction layer for tenant-related operations in a Django model.
    It defines a `_do_update()` method that filters base queries based on the
    current tenant and updates the model instances using the `super()` method.

    Attributes:
        objects (TenantManager): Used to manage the tenants for the model.
        tenant_id (str|int): Used to store the unique identifier for a tenant,
            which is used to filter related records when updating.

    """
    objects = TenantManager()
    tenant_id=''

    #adding tenant filters for save
    #Citus requires tenant_id filters for update, hence doing this below change.
    def _do_update(self, base_qs, using, pk_val, values, update_fields, forced_update):
        """
        Updates tenant records based on input parameters, taking into account
        current tenant and filtering the base query set with tenant-related fields.

        """
        current_tenant=get_current_tenant()
        if current_tenant:
            kwargs = { self.__class__.tenant_id: current_tenant.id}
            base_qs = base_qs.filter(**kwargs)
        return super(TenantModel,self)._do_update(base_qs, using, pk_val, values, update_fields, forced_update)

    class Meta:
        abstract = True


class TenantForeignKey(models.ForeignKey):
    """
    Modifies the behavior of a foreign key field to include tenant-specific data.
    It filters related instances based on the current tenant and adds a lookup
    condition for exact matching of tenant IDs.

    """

    # Override
    def get_extra_descriptor_filter(self, instance):
        """
        Returns a filter dictionary for the instance based on the current tenant
        ID, or warns about potential issues in a partitioned environment if no
        current tenant is set.

        Args:
            instance (selfmodel): Used to represent an instance of the model class.

        Returns:
            Dict[str,int]: A descriptor filter for the `TenantForeignKey` field
            on an instance of a model.

        """
        current_tenant = get_current_tenant()
        if current_tenant:
            return {instance.__class__.tenant_id: current_tenant.id}
        else:
            logger.warn('TenantForeignKey field %s.%s on instance "%s" '
                        'accessed without a current tenant set. '
                        'This may cause issues in a partitioned environment. '
                        'Recommend calling set_current_tenant() before accessing '
                        'this field.',
                        self.model.__name__, self.name, instance)
            return super(TenantForeignKey, self).get_extra_descriptor_filter(instance)

    # Override
    def get_extra_restriction(self, where_class, alias, related_alias):
        """
        Fetches tenant column names and fields for both sides of a relation, then
        creates a lookup condition and adds it to an existing where clause.

        Args:
            where_class (Type|Callable): Used to specify the condition for filtering
                related objects in the relation.
            alias (str): Used to specify the alias of the related model for the
                lookup operation.
            related_alias (str|List[str]): Used to specify the alias or aliases
                of the related model field that should be looked up in the related
                table.

        Returns:
            Condition: A subclass of the Python built-in `bool` type and represents
            a filter condition for use in a Django queryset.

        """

        # Fetch tenant column names for both sides of the relation
        lhs_model = self.model
        rhs_model = self.related_model
        lhs_tenant_id = lhs_model.tenant_id
        rhs_tenant_id = rhs_model.tenant_id

        # Fetch tenant fields for both sides of the relation
        lhs_tenant_field = lhs_model._meta.get_field(lhs_tenant_id)
        rhs_tenant_field = rhs_model._meta.get_field(rhs_tenant_id)

        # Get references to both tenant columns
        lookup_lhs = lhs_tenant_field.get_col(related_alias)
        lookup_rhs = rhs_tenant_field.get_col(alias)

        # Create "AND lhs.tenant_id = rhs.tenant_id" as a new condition
        lookup = lhs_tenant_field.get_lookup('exact')(lookup_lhs, lookup_rhs)
        condition = where_class()
        condition.add(lookup, 'AND')
        return condition



def get_current_user():
    """
    Despite arguments to the contrary, it is sometimes necessary to find out who is the current
    logged in user, even if the request object is not in scope.  The best way to do this is 
    by storing the user object in middleware while processing the request.
    """
    return getattr(_thread_locals, 'user', None)

def get_model_by_db_table(db_table):
    """
    Searches through the Django models registered in `apps` and returns the first
    model that matches the given `db_table`. If no match is found, it raises a `ValueError`.

    Args:
        db_table (str): The name of the database table associated with a model in
            Django's ORM.

    Returns:
        Model: A Django ORM model object associated with the given database table
        name.

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
    Retrieves the current tenant ID associated with the thread-local storage and
    returns it. If no tenant is set, it sets the default tenant.

    Returns:
        object: The current tenant associated with the thread-local storage.

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
    Maintains per-thread local variables for user and tenant information, and
    handles security-related issues by raising a `ValueError` when a user is created
    without a profile.

    """
    def process_request(self, request):
        """
        Sets the user and tenant variables for processing requests. If no profile
        is found with the user, an error message is raised to ensure security.

        Args:
            request (Any|Request): Possibly a valid Python object, used for executing
                code or making decisions based on its attributes or methods during
                the execution of the process.

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
