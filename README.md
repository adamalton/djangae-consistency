# Djangae Consistency

A library which helps to mitigate against eventual consistency issues with the App Engine Datastore.
Works only with [Djangae](https://github.com/potatolondon/djangae).


## Usage

```python
# models.py

import consistency # ensure that the signals get registered
```

```python
# views.py

from consistency import extend_queryset_with_recent_objects, get_recently_created_objects

# Example 1 - extending a queryset to include recently-created objects which also match it.
# Note that this causes your queryset to be evaluated.

def my_view(request):
    objects = MyModel.objects.filter(is_yellow=True)
    objects = extend_queryset_with_recent_objects(objects)
    return render(request, "my_template.html". {"objects": objects})


# Example 2 - getting a separate queryset of the recently-created objects which match it.


def my_view(request):
    objects = MyModel.objects.filter(is_yellow=True)
    new_objects = get_recently_created_objects(objects)
    return render(request, "my_template.html". {"objects": objects, "new_objects": new_objects})
```

Note that in both cases the recently-created objects are not guaranteed to be returned.  The
recently-created objects are only stored in memcache, which could be purged at any time.

# TODO

* Make an option to include whether to also cache recently *modified* objects so that they can be
  included in the cache of recent objects as well.  (Objects which previously didn't match the query
  may now match it but may not be returned by the normal Datastore query due to eventual consistency.)
* Add the option to only cache objects for specific models.
* In `extend_queryset_with_recent_objects` check that the queryset has a limit, and/or check that
  the total number of PKs is <= 1000 (the maximum for a Datastore Get).
