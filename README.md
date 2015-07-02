# Djangae Consistency

A Django app which helps to mitigate against eventual consistency issues with the App Engine Datastore.
Works only with [Djangae](https://github.com/potatolondon/djangae).


## Usage

```python
# models.py

import consistency # ensure that the signals get registered
```

```python
# views.py

from consistency import improve_queryset_consistency, get_recent_objects

# Example 1 - extending a queryset to include recently-created objects which also match it.
# Note that this causes your queryset to be evaluated.

def my_view(request):
    objects = MyModel.objects.filter(is_yellow=True)
    objects = improve_queryset_consistency(objects)
    return render(request, "my_template.html". {"objects": objects})


# Example 2 - getting a separate queryset of the recently-created objects which match it.


def my_view(request):
    objects = MyModel.objects.filter(is_yellow=True)
    new_objects = get_recent_objects(objects)
    return render(request, "my_template.html". {"objects": objects, "new_objects": new_objects})
```

Note that in both cases the recently-created objects are not guaranteed to be returned.  The
recently-created objects are only stored in memcache, which could be purged at any time.


## Advanced Configuration

By default the app will cache recently-created objects for all models.  But you can change this
behaviour so that it only caches particular models, only caches objects that match particular
criteria, and/or caches objects that were recently *modified* as well as recently *created* objects.

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
                # A list of checks, where each check is a dict of filter kwargs or a function.
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


## Notes

* Even if you set both `cache_on_creation` and `cache_on_modification` to `False`, you can still use
`improve_queryset_consistency` to prevent stale objects from being returned by your query.
* Using the "session" cache may be slightly faster for querying (as the session object has probably
  been loaded anyway, so it avoids another cache lookup), but it's unlikely to be faster when
  creating/modifying an object, because writing to the session requires a Database write, which is
  probably slower than a cache write.  Unless you're altering the session object anyway, in which
  case the session cache may be advantageous.

# TODO

* Make an option to include whether to also cache recently *modified* objects so that they can be
  included in the cache of recent objects as well.  (Objects which previously didn't match the query
  may now match it but may not be returned by the normal Datastore query due to eventual consistency.)
* Add the option to only cache objects for specific models.
* In `improve_queryset_consistency` check that the queryset has a limit, and/or check that
  the total number of PKs is <= 1000 (the maximum for a Datastore Get).
