""" A module which helps prevent eventual consistency issues on the Datastore. """

# SYSTEM
import logging

# 3RD PARTY
from django.conf import settings
from django.db import models
from django.dispatch import receiver

# CONSISTENCY
from .caches import get_caches


DEFAULT_CONFIG = {
    "cache_on_creation": True,
    "cache_on_modification": False,
    "cache_time": 60, # seconds
    "caches": ["django"],
    "only_cache_matching": [],
}



########################## API ##########################

def improve_queryset_consistency(queryset):
    """ Makes a queryset eventual-consistency-resistant (but not immune to it) by:
        1. Explicitly including PKs of recently-created/-modified objects (if they match the query).
        2. Re-fetching each object by PK to ensure that we get the latest version and exclude
           objects which no longer match the query.
    """
    # By using pk__in we cause the objects to be re-fetched with datastore.Get so we get the
    # up-to-date version of every object
    pks = list(queryset.values_list('pk', flat=True)) # this may exclude recently-created objects
    recent_pks = get_recent_object_pks_for_model(queryset.model)
    combined_pks = list(set(pks + recent_pks))
    # we keep the original filtering as well so that objects which don't match the query are excluded
    return queryset.filter(pk__in=combined_pks)


def get_recent_objects(queryset):
    """ Get and return a queryset of recently-created/-modified objects which match the given queryset.
        You can append/include/merge this with the results of the original queryset as you wish.
        Note that this may include objects which are also returned by your original queryset.
    """
    return queryset.filter(pk__in=get_recent_object_pks_for_model(queryset.model))

######################## SIGNALS ########################


@receiver(models.signals.post_save)
def handle_post_save(sender, instance, created, **kwargs):
    config = get_config(sender)
    if should_cache(instance, created, config):
        add_object_pk_to_caches(instance, config)


@receiver(models.signals.post_delete)
def handle_post_delete(sender, instance, **kwargs):
    config = get_config(sender)
    if might_be_cached(sender, config):
        remove_object_pk_from_caches(instance, config)


#########################################################


def get_config(model_class):
    """ Get the config for the given model class. """
    model_identifier = u"%s.%s" % (model_class._meta.app_label, model_class._meta.model_name)
    config = DEFAULT_CONFIG.copy()
    overrides = getattr(settings, "CONSISTENCY_CONFIG", {})
    config.update(overrides.get("defaults", {}))
    config.update(overrides.get("models", {}).get(model_identifier, {}))
    return config


def should_cache(obj, created, config):
    if created:
        if not config["cache_on_creation"]:
            return False
    else:
        if not config["cache_on_modification"]:
            return False
    if not config["only_cache_matching"]:
        return True
    return object_matches_a_check(obj, config["only_cache_matching"])


def might_be_cached(obj, config):
    """ Might the given object be cached? """
    if not (config["cache_on_creation"] or config["cache_on_modification"]):
        return False
    if not config["only_cache_matching"]:
        return True
    return object_matches_a_check(obj, config["only_cache_matching"])


def object_matches_a_check(obj, checks):
    """ Does the object match *any* of the given checks from the "only_cache_matching" list? """
    for check in checks:
        if callable(check):
            if check(obj):
                return True
        else:
            try:
                for field, value in check.iteritems():
                    if not getattr(obj, field) == value:
                        break
                else:
                    return True
            except AttributeError:
                logging.error("Invalid filter for model %s, %s", obj.__class__, check)
                raise
    return False


def get_recent_object_pks_for_model(model_class):
    config = get_config(model_class)
    cache_key = get_model_cache_key(model_class)
    pks = set()
    for cache in get_caches(config["caches"]):
        pks.update(cache.get_pks(model_class, config, cache_key))
    return list(pks)


def add_object_pk_to_caches(obj, config):
    cache_key = get_model_cache_key(obj.__class__)
    for cache in get_caches(config["caches"]):
        cache.add(obj, config, cache_key)


def remove_object_pk_from_caches(obj, config):
    cache_key = get_model_cache_key(obj.__class__)
    for cache in get_caches(config["caches"]):
        cache.remove(obj, config, cache_key)


def get_model_cache_key(model_class):
    return "recently-created-{0}-{1}".format(model_class._meta.app_label, model_class._meta.db_table)
