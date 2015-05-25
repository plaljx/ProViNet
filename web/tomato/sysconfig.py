# -*- coding: utf-8 -*-

# ToMaTo (Topology management software) 
# Copyright (C) 2012 Integrated Communication Systems Lab, University of Kaiserslautern
#
# This file is part of the ToMaTo project
#
# ToMaTo is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

#from django.http import HttpResponseRedirect
from datetime import datetime
import pytz
from django.shortcuts import render
from django import forms
from django.conf import settings  # noqa
from django import shortcuts
from django import http
from django.utils import translation
from admin_common import BootstrapForm, Buttons
from tomato.crispy_forms.layout import Layout
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from lib import wrap_rpc

'django.core.context_processors.i18n',

TEMPLATE_CONTEXT_PROCESSORS = (
    'tools.context_processors.set',
    'django.core.context_processors.request',
    'django.core.context_processors.auth',
    'django.core.context_processors.i18n',
)



def _one_year():
    now = datetime.utcnow()
    return datetime(now.year + 1, now.month, now.day, now.hour,
                    now.minute, now.second, now.microsecond, now.tzinfo)

class SysConfigForm(BootstrapForm):
        language = forms.ChoiceField(label=_("Language"))
        timezone = forms.ChoiceField(label=_("Timezone"))
        allocation_policy = forms.ChoiceField(label=_("Allocation policy"))
        def __init__(self, *args, **kwargs):
                super(SysConfigForm, self).__init__(*args, **kwargs)

                def get_language_display_name(code, desc):
                    try:
                        desc = translation.get_language_info(code)['name_local']
                    except KeyError:
                        # If a language is not defined in django.conf.locale.LANG_INFO
                        # get_language_info raises KeyError
                        pass
                    return "%s (%s)" % (desc, code)
                languages = [(k, get_language_display_name(k, v))
                             for k, v in settings.LANGUAGES]
                self.fields['language'].choices = languages
                #print languages
                d = datetime(datetime.today().year, 1, 1)
                timezones = []
                for tz in pytz.common_timezones:
                   try:
                       utc_offset = pytz.timezone(tz).localize(d).strftime('%z')
                       utc_offset = " (UTC %s:%s)" % (utc_offset[:3], utc_offset[3:])
                   except Exception:
                        utc_offset = ""

                   if tz != "UTC":
                       tz_name = "%s%s" % (tz, utc_offset)
                   else:
                      tz_name = tz
                   timezones.append((tz, tz_name))

                self.fields['timezone'].choices = timezones

                allocation_policy_data = [('rand', u'random'), ('desi', u'designated'),('load',u'load'),('effi',u'efficiency')] 
#                allocation_policy_data = [('load'),('efficiency'),('host')] 
                self.fields['allocation_policy'].choices = allocation_policy_data

                self.helper.form_action = reverse(config)
                self.helper.layout = Layout(
                        'language',
                        'timezone',
                        'allocation_policy',
                        Buttons.cancel_save
                )

@wrap_rpc
def config(api, request):
	if request.method == "GET":
		allocation_policy = api.getAllocationPolicy()
        	form = SysConfigForm(initial={"language":request.LANGUAGE_CODE,"timezone":request.COOKIES.get('django_timezone', 'UTC'),"allocation_policy":allocation_policy})
        	response = render(request, "form.html", {"form": form, "heading": _("System Setting")})
		return response
        if request.method == "POST":
		response = shortcuts.redirect(request.build_absolute_uri())
		language = request.POST.get('language',None)
		time = request.POST.get('timezone',None)
		allocation_policy = request.POST.get('allocation_policy',None)
		if language and translation.check_for_language(language):
			if hasattr(request, 'session'):
				request.session['django_language'] = language
        			form = SysConfigForm(request.REQUEST)
			response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language, expires=_one_year())
		request.session['django_timezone'] = pytz.timezone(time).zone

		response.set_cookie('django_timezone', time,
                                  expires=_one_year())
		api.setAllocationPolicy(allocation_policy)

       #                 with translation.override(language):
        #                			messages = _("Setting saved.")
		return response
