from functools import partial

from django import forms
from django.forms.util import flatatt
from google.appengine.ext import db
from webob.multidict import UnicodeMultiDict

from . import admin_settings, render


class ReferenceSelect(forms.widgets.Select):
    """Customized Select widget that adds link "Add new" near dropdown box.
        This widget should be used for ReferenceProperty support only.
    """
    def __init__(self, reference_kind='', *attrs, **kwattrs):
        super(ReferenceSelect, self).__init__(*attrs, **kwattrs)
        self.reference_kind = reference_kind

    def render(self, *attrs, **kwattrs):
        output = super(ReferenceSelect, self).render(*attrs, **kwattrs)
        return output + u'\n<a href="%s/%s/new/" target="_blank">Add new</a>' % (admin_settings.ADMIN_BASE_URL, self.reference_kind)


class FileInput(forms.widgets.Input):
    """Customized FileInput widget that shows downlaod link for uploaded file.
    """
    input_type = 'file'
    needs_multipart_form = True
    download_url_template = '<a href="%(base_url)s/%(model_name)s/get_blob_contents/%(field_name)s/%(itemKey)s/">File uploaded: %(fileName)s</a>&nbsp;'

    def __init__(self, *args, **kwargs):
        super(FileInput, self).__init__(*args, **kwargs)
        self.model_name = ''
        self.field_name = ''
        self.itemKey = ''
        self.fileName = ''
        self.show_download_url = False
        self.__args = args
        self.__kwargs = kwargs

    def __copy__(self):
        return FileInput(*self.__args, **self.__kwargs)

    def render(self, name, value, attrs=None):
        """Overrides render() method in order to attach file download
            link if file already uploaded.
        """
        output = super(FileInput, self).render(name, None, attrs=attrs)
        # attach file download link
        if self.show_download_url:
            output = self.download_url_template % {
                'base_url': admin_settings.ADMIN_BASE_URL,
                'model_name': self.model_name,
                'field_name': self.field_name,
                'itemKey': self.itemKey,
                'fileName': self.fileName,
            } + output
        return output

    def value_from_datadict(self, data, files, name):
        "File widgets take data from FILES, not POST"
        return data.get(name, None)

    def _has_changed(self, initial, data):
        if data is None:
            return False
        return True


class SelectMultiple(forms.SelectMultiple):
    def value_from_datadict(self, data, files, name):
        if isinstance(data, UnicodeMultiDict):
            return data.getall(name)
        return data.get(name, None)
## END Django 1.0 widgets


class AjaxListProperty(forms.Widget):
  def render(self, name, value, attrs=None):
    objects = []
    object_classes = {}

    keys = value or []
    for key in keys:
      if not key:
        continue
      # Turn string keys into Key objects
      if isinstance(key, basestring):
        key = db.Key(key)
      obj = db.get(key)
      objects.append((key, obj))
      object_classes[obj.__class__.__name__] = obj.__class__

    final_attrs = self.build_attrs(attrs, name=name)
    flat_attrs = flatatt(final_attrs)

    from .handlers import AdminHandler
    handler = AdminHandler()

    return render.template('widgets/ajax_list_property.html', {
      'flat_attrs': flat_attrs,
      'objects': objects,
      'object_classes': object_classes,
      'get_item_edit_url': partial(get_item_edit_url, handler=handler),
      'name': name,
      'paged_selector': partial(paged_selector, handler=handler),
    })

  def value_from_datadict(self, data, files, name):
    if isinstance(data, UnicodeMultiDict):
      return data.getall(name)

    from django.utils.datastructures import MultiValueDict, MergeDict
    if isinstance(data, (MultiValueDict, MergeDict)):
      return data.getlist(name)

    data_list = data.get(name, None)
    if isinstance(data, (list, tuple)):
      return data_list
    return [data_list]

  def _has_changed(self, initial, data):
    # TODO: implement properly
    from django.utils.encoding import force_unicode
    if initial is None:
      initial = []
    if data is None:
      data = []
    if len(initial) != len(data):
      return True
    initial_set = set([force_unicode(value) for value in initial])
    data_set = set([force_unicode(value) for value in data])
    return data_set != initial_set


def get_item_edit_url(model_instance, handler):
  return handler.uri_for('appengine_admin.edit', model_name=model_instance.__class__.__name__, key=model_instance.key())


def paged_selector(cls, handler):
  from . import model_register
  from .utils import Paginator
  model_admin = model_register.get_model_admin(cls.__name__)
  base_url = handler.uri_for('appengine_admin.list', model_name=cls.__name__)
  return Paginator(model_admin).get_page({}, base_url=base_url)
