# Import <anything> from consistency.py so that our signals get registered

# TODO: move these into a signals.py file and use the ready() function when on Django >= 1.7
from .consistency import handle_post_save, handle_post_delete
