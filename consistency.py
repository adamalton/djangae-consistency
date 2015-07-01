""" A module which helps prevent eventual consistency issues on the Datastore. """

import datetime
import itertools
from django.core.cache import cache
from django.db import models
from django.dispatch import receiver
from django.utils import timezone


RECENTLY_CREATED_OBJECTS_CACHE_TIME = 60 * 5 # 5 MINUTES



########################## API ##########################

def make_queryset_consistent(queryset):
    """ Makes a queryset eventual-consistency-proof by:
        1. Explicitly including PKs of recently-created objects (if they match the query).
        2. Re-fetching each object by PK to ensure that we get the latest version.
    """
    new = queryset.model._default_manager.all()
    # By using pk__in we cause the objects to be re-fetched with datastore.Get so we get the
    # up-to-date version of every object
    pks = list(queryset.values_list('pk', flat=True)) # this may exclude recently-created objects
    recent_pks = [pk for pk in get_recently_created_object_pks_for_model(queryset.model) if pk not in pks]
    refreshed_objects = new.filter(pk__in=pks)
    new_objects = queryset.filter(pk__in=recent_pks)
    return itertools.chain(refreshed_objects, new_objects)


######################## SIGNALS ########################


@receiver(models.signals.post_save)
def cache_new_object(sender, instance, created, **kwargs):
    if created:
        add_object_to_recently_created_cache(instance)


@receiver(models.signals.post_delete)
def uncache_deleted_object(sender, instance, **kwargs):
    remove_object_from_recently_created_cache(instance)


#########################################################

# You're unlikely to need to directly use functions below here


def get_recently_created_object_pks_for_model(model_class):
    cache_key = get_recently_created_objects_cache_key(model_class)
    objects = cache.get(cache_key) or {}
    return objects.keys()


def add_object_to_recently_created_cache(obj):
    cache_key = get_recently_created_objects_cache_key(obj.__class__)
    objects = cache.get(cache_key) or {}
    # take the opportunity to prune our cache of any objects which were created a while
    # ago and should therefore now be being returned by the Datastore
    objects = strip_old_objects(objects)
    objects[obj.pk] = timezone.now()
    cache.set(cache_key, objects) # TODO use check and set to make this transactional


def remove_object_from_recently_created_cache(obj):
    cache_key = get_recently_created_objects_cache_key(obj.__class__)
    objects = cache.get(cache_key) or {}
    # take the opportunity to prune our cache of any objects which were created a while
    # ago and should therefore now be being returned by the Datastore
    updated_objects = strip_old_objects(objects)
    try:
        del updated_objects[obj.pk]
    except KeyError:
        pass
    if updated_objects != objects:
        # only update the cache if it's changed
        cache.set(cache_key, objects) # TODO use check and set to make this transactional


def get_recently_created_objects_cache_key(model_class):
    return "recently-created-{0}-{1}".format(model_class._meta.app_label, model_class._meta.db_table)


def strip_old_objects(objects):
    to_keep = {}
    threshold = timezone.now() - datetime.timedelta(seconds=RECENTLY_CREATED_OBJECTS_CACHE_TIME)
    for obj_pk, created_time in objects.items():
        if created_time >= threshold:
            # object is still new enough to keep in the cache
            to_keep[obj_pk] = created_time
    return to_keep
