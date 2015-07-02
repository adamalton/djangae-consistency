# Djangae Consistency

A Django app which helps to mitigate against eventual consistency issues with the App Engine Datastore.
Works only with [Djangae](https://github.com/potatolondon/djangae).


## In A Nutshell

It caches recently created and/or modified objects so that it knows about them even if they're not
yet being returned by the Datastore.  It then provides a function `improve_queryset_consistency`
which you can use on a queryset so that it:

* Uses the cache to include recently-created/-modified objects which match the query but which are
  not yet being returned by the Datastore. (This is not effective if the cache gets purged).
* Does not return any recently deleted objects which are still being returned by the Datastore.
  (This is not cache-dependent.)


## Usage

Add `'consistency'` to `settings.INSTALLED_APPS` and then use as follows.  (You may also need to
import `consistency.models` to get the signals to register.)

```python

from consistency import improve_queryset_consistency, get_recent_objects

# Example 1 - `improve_queryset_consistency`

queryset = MyModel.objects.filter(is_yellow=True)
more_consistent_queryset = improve_queryset_consistency(queryset)
# Use as normal


# Example 2 - `get_recent_objects`

queryset = MyModel.objects.filter(is_yellow=True)
objects_possibly_missed = get_recent_objects(queryset)
# Use both together to build your full set of results

```

Note that in both cases the recently-created objects are not guaranteed to be returned.  The
recently-created objects are only stored in memcache, which could be purged at any time.


## Advanced Configuration

By default the app will cache recently-created objects for all models.  But you can change this
behaviour so that it only caches particular models, only caches objects that match particular
criteria, and/or caches objects that were recently *modified* as well as recently *created*.

```python
CONSISTENCY_CONFIG = {

    # These defaults apply to every model, unless otherwise overriden
    "defaults": {
        "cache_on_creation": True,
        "cache_on_modification": False,
        "cache_time": 60, # seconds
        "caches": ["django", "session"],
    },

    # The settings can be overridden for each individual model
    "models": {
        "app_name.ModelName": {
            "cache_on_creation": True,
            "cache_on_modification": True,
            "caches": ["session", "django"],
            "cache_time": 20,
            "only_cache_matching": [
                # A list of checks, where each check is a dict of
                # filter kwargs or a function.
                # If an object matches *any* of these then it is cached.
                {"name": "Ted", "archived": False},
                lambda obj: obj.method(),
            ]
        },
        "app_name.UnimportantModel": {
            "cache_on_creation": False,
            "cache_on_modification": False,
        },
    },
}
```


## Notes

* Even if you set both `cache_on_creation` and `cache_on_modification` to `False`, you can still use
  `improve_queryset_consistency` to prevent stale objects from being returned by your query.
* The way that `improve_queryset_consistency` works means that it converts your query into a
  `pk__in` query.  This has 2 side effects:
    - It causes the initial query to be executed.  It does this with `values_list('pk')` (which
      becomes a Datastore keys-only query) so is fast, but you should be aware that it hits the DB.
    - It introduces a limit of 1000 results, so if your queryset is not already limited then a
      limit will be imposed, and if your queryset already has a limit then it may be reduced. This
      is to ensure a total result of <= 1000 objects.  This is imperfect though, and may result in
      slightly fewer than 1000 results because recent objects in the cache will reduce the limit
      even if they don't match the query. (This could potentially be fixed.)
* To avoid the side effects of `improve_queryset_consistency` you may wish to use
  `get_recent_objects` instead, giving you slightly more control over what happens.
* Using the "session" cache may be slightly faster for querying (as the session object has probably
  been loaded anyway, so it avoids another cache lookup), but it's unlikely to be faster when
  creating/modifying an object, because writing to the session requires a Database write, which is
  probably slower than a cache write.  Unless you're altering the session object anyway, in which
  case the session cache may be advantageous.
